import os
import time
import shutil
import logging
from pathlib import Path
from functools import partial
from tempfile import NamedTemporaryFile
from subprocess import check_output, CalledProcessError, STDOUT

from qtpy.QtCore import Signal, Slot
from qtpy import QtMultimedia

from scdv.ui import qtc, qtw, qtg
from scdv import CONTRIB_DIR, get_scdv
from scdatatools.cry.cryxml import is_cryxmlb_file, dict_from_cryxml_string
from scdatatools.wwise.utils import wwise_id_for_string
from scdatatools.utils import dict_search
from scdv.ui.widgets.dock_widgets.common import icon_provider, SCDVSearchableTreeDockWidget
from scdv.utils import show_file_in_filemanager
from scdv.ui.utils import ScrollMessageBox, ContentItem, seconds_to_str
from scdv.resources import RES_PATH
from scdv.ui.widgets.dock_widgets.sc_archive import SCFileViewModel

logger = logging.getLogger(__file__)

SCAUDIOVIEWW_COLUMNS = ['Name']

GAME_AUDIO_P4K_RELPATH = Path('Data/Libs/')
GAME_AUDIO_P4K_SEARCH = str(GAME_AUDIO_P4K_RELPATH / 'GameAudio' / '*.xml')
GAME_AUDIO_DCB_SEARCH = 'libs/foundry/records/musiclogic/*'

WW2OGG = shutil.which('ww2ogg.exe')
REVORB = shutil.which('revorb.exe')
if WW2OGG is None and (CONTRIB_DIR / 'ww2ogg.exe').is_file():
    WW2OGG = Path(CONTRIB_DIR / 'ww2ogg.exe')
else:
    WW2OGG = Path(WW2OGG)
if REVORB is None and (CONTRIB_DIR / 'revorb.exe').is_file():
    REVORB = Path(CONTRIB_DIR / 'revorb.exe')
else:
    REVORB = Path(REVORB)


class LoaderSignals(qtc.QObject):
    cancel = Signal()
    finished = Signal()


class SCAudioViewLoader(qtc.QRunnable):
    def __init__(self, scdv, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv
        self.model = model
        self.signals = LoaderSignals()
        self._node_cls = SCP4kAudioViewNode
        self._should_cancel = False
        self.signals.cancel.connect(self._handle_cancel)

    def _handle_cancel(self):
        self._should_cancel = True

    def run(self):
        ga_files = self.scdv.sc.p4k.search(GAME_AUDIO_P4K_SEARCH)
        self.scdv.task_started.emit('load_gameaudio', 'Loading Game Audio', 0, len(ga_files))

        t = time.time()
        wwise = self.scdv.sc.wwise
        self.scdv.update_status_progress.emit('load_gameaudio', 0, 0, len(wwise.preloads), '')
        for i, p4kfile in enumerate(ga_files):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_gameaudio', i, 0, 0, '')
                t = time.time()
            wwise.load_game_audio_file(self.scdv.sc.p4k.open(p4kfile))

        self.scdv.update_status_progress.emit('load_gameaudio', 0, 0, len(wwise.preloads), 'Parsing Game Audio')
        for i, p in enumerate(wwise.preloads):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_gameaudio', i, 0, 0, '')
                t = time.time()

            base_path = Path('GameAudio') / p
            preload = wwise.preloads[p]
            atl_names = list(preload['triggers'].keys()) + list(preload['external_sources'].keys())
            if atl_names:
                self.model.appendRowsToPath(base_path, [
                    self._node_cls(base_path / atl_name, atl_name=atl_name)
                    for atl_name in atl_names
                ])

        self.scdv.task_finished.emit('load_gameaudio', True, '')
        self.signals.finished.emit()


class SCP4kAudioViewNode(qtg.QStandardItem, ContentItem):
    def __init__(self, path: Path, atl_name=None, *args, **kwargs):
        super().__init__(path.stem, *args, **kwargs)
        ContentItem.__init__(self, path.stem, path)
        self.atl_name = atl_name
        self._wems = []
        self._wems_loaded = False

    @property
    def wems(self):
        if self.atl_name and not self._wems_loaded:
            self._wems = list(get_scdv().sc.wwise.wems_for_atl_name(self.atl_name).keys())
            self._wems_loaded = True
        return self._wems

    def highlight(self, should_highlight=True):
        if should_highlight:
            self.setBackground(qtc.Qt.darkGray)
        else:
            self.setBackground(qtg.QBrush())


class SCAudioViewModel(SCFileViewModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColumnCount(len(SCAUDIOVIEWW_COLUMNS))
        self.setHorizontalHeaderLabels(SCAUDIOVIEWW_COLUMNS)
        self._node_cls = SCP4kAudioViewNode

    def flags(self, index):
        return super().flags(index) & ~qtc.Qt.ItemIsEditable


class AudioViewDock(SCDVSearchableTreeDockWidget):
    __ui_file__ = str(RES_PATH / 'ui' / 'AudioViewDock.ui')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Audio'))
        self.scdv.p4k_loaded.connect(self.handle_p4k_opened)
        self.handle_p4k_opened()  # check if the p4k is opened

        self._currently_playing = None
        self._currently_playing_wem_id = None
        self._wem_list_item = None
        self._playlist_index = (0, 0)
        self._playlist = []
        self._auto_play = True
        self._audio_buffer = None
        self._audio_tmp = None
        self._media_player = QtMultimedia.QMediaPlayer(self)

        self._media_player.durationChanged.connect(self._handle_duration_changed)
        self._media_player.positionChanged.connect(self._handle_position_changed)
        self._media_player.stateChanged.connect(self._handle_state_changed)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setSizes([1024, 50])
        self.wem_list.hide()

        # self.wem_list.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        # self.wem_list.customContextMenuRequested.connect(self._show_ctx_menu)
        self.wem_list.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.wem_list.doubleClicked.connect(self._on_wem_doubleclick)

        self.playButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaPlay))
        self.playButton.clicked.connect(lambda b: self.play())  # lambda consumes the checked bool
        self.pauseButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaPause))
        self.pauseButton.clicked.connect(self.pause)
        self.pauseButton.hide()
        self.prevButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaSkipBackward))
        self.prevButton.clicked.connect(self.play_previous)
        self.stopButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaStop))
        self.stopButton.clicked.connect(self.stop)
        self.nextButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaSkipForward))
        self.nextButton.clicked.connect(self.play_next)

        self.sc_breadcrumbs.setVisible(True)
        self.gotoButton.clicked.connect(self._handle_goto)
        self.play_info.setVisible(False)

        # self.playbackSlider.sliderPressed.connect(self._handle_playback_pressed)
        self.playbackSlider.sliderReleased.connect(self._handle_playback_released)
        # TODO: handle saving the volume setting in the settings
        self.volumeDial.sliderMoved.connect(self.set_volume)
        self.set_volume(75)

        self.ctx_manager.default_menu.addSeparator()
        extract = self.ctx_manager.default_menu.addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        extract = self.ctx_manager.menus[''].addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))

    def destroy(self, *args, **kwargs) -> None:
        if self._audio_tmp is not None:
            self._audio_tmp.unlink()
        return super().destroy(*args, **kwargs)

    def _handle_playback_released(self):
        self._media_player.setPosition(self.playbackSlider.value())

    def _handle_duration_changed(self, duration):
        self.durationLabel.setText(seconds_to_str(duration / 1000))
        self.playbackSlider.setMaximum(duration)

    def _handle_position_changed(self, position):
        self.positionLabel.setText(seconds_to_str(position / 1000))
        self.playbackSlider.setValue(position)

    def _handle_state_changed(self, state):
        if self._currently_playing is not None:
            self.play_info.setVisible(True)
            self._currently_playing.highlight(False)
        else:
            self.play_info.setVisible(False)
        if self._currently_playing_wem_id is not None:
            self._highlight_wem(self._currently_playing_wem_id, False)

        playlist_index, wem_index = self._playlist_index
        if len(self._currently_playing.wems) > 1:
            wem_txt = f' [{self._currently_playing_wem_id + 1}/{len(self._currently_playing.wems)}]'
        else:
            wem_txt = ''
        if self._playlist:
            self.sc_breadcrumbs.setText(f'{playlist_index + 1}/{len(self._playlist)} - '
                                        f'{self._currently_playing.name}{wem_txt}')
        else:
            self.sc_breadcrumbs.setText(f'{self._currently_playing.name}{wem_txt}')

        if state == QtMultimedia.QMediaPlayer.State.PlayingState:
            self.playButton.hide()
            self.pauseButton.show()
            if self._currently_playing is not None:
                self._currently_playing.highlight(True)
            if self._currently_playing_wem_id is not None:
                self._highlight_wem(self._currently_playing_wem_id, True)
        else:
            self.playButton.show()
            self.pauseButton.hide()

        if state == QtMultimedia.QMediaPlayer.State.StoppedState and self._playlist and self._auto_play:
            self.play_next()

    def _handle_goto(self):
        if self._currently_playing:
            tree_item = self.proxy_model.mapFromSource(self._currently_playing.index())
            self.sc_tree.expand(tree_item)
            self.sc_tree.scrollTo(tree_item)

    def _change_media(self, item, wem_id):
        """ Returns the item if set correctly, else None """
        if item.atl_name is None or not item.wems:
            return None

        # Using a buffer causes qmediaplayer to crash after a changing files a bunch - so moved to using temp files on
        # disk. leaving this here for posterity
        # if self._audio_buffer is not None:
        #     self._media_player.setMedia(QtMultimedia.QMediaContent())
        #     if self._audio_buffer.isOpen():
        #         self._audio_buffer.close()
        # self._audio_buffer.setData(item.contents())
        # if self._audio_buffer.open(qtc.QIODevice.ReadOnly):
        #     self._media_player.setMedia(QtMultimedia.QMediaContent(), self._audio_buffer)
        #     return item
        # else:
        #     logger.error(f'Failed to open new audio buffer')

        if self._audio_tmp is not None:
            self._media_player.setMedia(QtMultimedia.QMediaContent())
            time.sleep(0.5)
            self._audio_tmp.unlink()
            self._audio_tmp = None
        self._audio_tmp = self.scdv.sc.wwise.convert_wem(item.wems[wem_id], return_file=True)
        self._currently_playing = item
        self._currently_playing_wem_id = wem_id
        self._media_player.setMedia(qtc.QUrl.fromLocalFile(str(self._audio_tmp.absolute())))

    def set_volume(self, level):
        self._media_player.setVolume(level)
        self.volumeDial.setValue(level)

    def _update_wem_list(self, item):
        self.wem_list.clear()
        if item.wems:
            self.wem_list.addItems(item.wems)
            self._wem_list_item = item
            self.wem_list.show()

    def play(self, item=None, wem_id=0):
        if item is None:
            if not self._currently_playing:
                return
            item = self._currently_playing
        if item.atl_name is None:
            return

        if self._playlist:
            self._auto_play = True

        if self._wem_list_item != item:
            self._update_wem_list(item)

        if item != self._currently_playing or wem_id != self._currently_playing_wem_id:
            self._change_media(item, wem_id)
        if item == self._currently_playing and wem_id == self._currently_playing_wem_id:

            wem_item = self.wem_list.item(self._currently_playing_wem_id)
            self.wem_list.scrollToItem(wem_item)
            self._media_player.play()

    def pause(self):
        self._media_player.pause()

    def play_previous(self):
        # if a playlist and in the first two seconds, play the previous track in the playlist
        self.stop()
        # self._media_player.position() always returns 0, so use the playbackSlider value which is updated
        if self._playlist and self.playbackSlider.value() < 2000:
            playlist_index, wem_index = self._playlist_index
            try:
                if wem_index > 0:
                    wem_index -= 1
                else:
                    playlist_index = max(0, self._playlist.index(self._currently_playing) - 1)
                    wem_index = max(0, len(self._playlist[playlist_index].wems) - 1)
            except ValueError:
                playlist_index = 0
                wem_index = 0

            self._playlist_index = (playlist_index, wem_index)
            if playlist_index <= len(self._playlist):
                self.play(self._playlist[playlist_index], wem_index)
        else:
            # just play the same sound again if not playlist
            self._media_player.play()

    def stop(self):
        self._auto_play = False
        self._media_player.stop()

    def play_next(self):
        self.stop()
        if self._playlist:
            playlist_index, wem_index = self._playlist_index
            try:
                wem_index += 1
                if wem_index >= len(self._playlist[playlist_index].wems):
                    wem_index = 0
                    playlist_index = self._playlist.index(self._currently_playing) + 1
            except ValueError:
                wem_index = 0
                playlist_index = 0

            if playlist_index < len(self._playlist):
                self._playlist_index = (playlist_index, wem_index)
                self.play(self._playlist[playlist_index], wem_index)
            else:
                self._playlist_index = (len(self._playlist) - 1, 0)

    @Slot()
    def _finished_loading(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        self.raise_()

    def handle_p4k_opened(self):
        if self.scdv.sc is not None and self.scdv.sc.is_loaded:
            self.show()
            self.sc_tree_model = SCAudioViewModel(self.scdv.sc, parent=self)
            loader = SCAudioViewLoader(self.scdv, self.sc_tree_model)
            self.closing.connect(lambda: loader.signals.cancel.emit())
            loader.signals.finished.connect(self._finished_loading)
            self.sc_tree_thread_pool.start(loader)

    def _handle_item_action(self, item, model, index):
        self.stop()
        if item.atl_name:
            if item in self._playlist:
                self._playlist_index = (self._playlist.index(item), 0)
            else:
                self._playlist = []
            self.play(item, wem_id=0)
        else:
            self._currently_playing = None
            self._currently_playing_wem_id = None
            self._playlist_index = (0, -1)
            self._playlist = [item for item in self.get_selected_items() if item.atl_name is not None]
            self.play_next()

    @Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = [_ for _ in self.get_selected_items() if _.atl_name is not None]

        # Item Actions
        if not selected_items:
            return

        if action == 'extract':
            edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Extract to...')
            if edir:
                total = len(selected_items)
                self.scdv.task_started.emit('extract_audio', f'Extracting Game Audio to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    self.scdv.update_status_progress.emit('extract_audio', 1, 0, total,
                                                          f'Extracting {item.name} to {edir}')
                    base_out = Path(edir) / item.parent().name
                    for wem in item.wems:
                        try:
                            outfile = base_out / f'{item.atl_name}_{wem}.ogg'
                            outfile.parent.mkdir(parents=True, exist_ok=True)
                            tmp = self.scdv.sc.wwise.convert_wem(wem, return_file=True)
                            shutil.move(tmp, outfile)
                        except Exception as e:
                            logger.exception(f'Exception extracting wem {item.atl_name}.{wem}', exc_info=e)

                self.scdv.task_finished.emit('extract_audio', True, '')
                show_file_in_filemanager(Path(edir))

    def _on_wem_doubleclick(self, index):
        if self._currently_playing:
            self.stop()
            if self._currently_playing in self._playlist:
                self._playlist_index = (self._playlist.index(self._currently_playing), index.row())
            else:
                self._playlist = []
            self.play(self._currently_playing, index.row())

    def _highlight_wem(self, row, should_highlight):
        item = self.wem_list.item(row)
        if item is not None:
            if should_highlight:
                item.setBackground(qtc.Qt.darkGray)
            else:
                item.setBackground(qtg.QBrush())
