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

from scdv import CONTRIB_DIR
from scdv.ui import qtc, qtw, qtg
from scdatatools.cry.cryxml import is_cryxmlb_file, dict_from_cryxml_string
from scdatatools.wwise.bnk import SoundBank
from scdatatools.wwise import wwise_id_for_string
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
        tmp = {}
        ga_files = list(self.scdv.sc.p4k.search(GAME_AUDIO_P4K_SEARCH))
        self.scdv.task_started.emit('load_gameaudio', 'Parsing Game Audio', 0, len(ga_files))
        t = time.time()

        wems = {Path(_.filename).stem: _ for _ in self.scdv.sc.p4k.search('Data/Sounds/wwise/*.wem')}
        bnks = {Path(_.filename).name: _ for _ in self.scdv.sc.p4k.search('Data/Sounds/wwise/*.bnk')}
        found = set()

        for i, f in enumerate(ga_files):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_gameaudio', i, 0, 0, '')
                t = time.time()

            try:
                base_path = Path(f.filename.split('.', maxsplit=1)[0]).relative_to(GAME_AUDIO_P4K_RELPATH)
                raw = self.scdv.sc.p4k.open(f).read()
                if is_cryxmlb_file(raw):
                    ga = dict_from_cryxml_string(raw)
                    ga_bnk = ga.get('ATLConfig',
                                    {}).get('AudioPreloads',
                                            {}).get('ATLPreloadRequest',
                                                    {}).get('ATLConfigGroup',
                                                            {}).get('WwiseFile')
                    if ga_bnk is None:
                        continue

                    try:
                        bnk = SoundBank(self.scdv.sc.p4k.open(bnks[ga_bnk['@wwise_name']]).read())
                    except Exception as e:
                        logger.warning(f'Skipping GameAudio {f.filename}, invalid SoundBank "{ga_bnk["@wwise_name"]}"')
                        continue

                    atl_triggers = ga.get('ATLConfig', {}).get('AudioTriggers', {}).get('ATLTrigger', [])
                    if isinstance(atl_triggers, dict):
                        atl_triggers = [atl_triggers]
                    for trigger in atl_triggers:
                        atl_name = trigger.get('@atl_name', '')
                        if not atl_name:
                            continue

                        trigger_id = wwise_id_for_string(atl_name)
                        event = bnk.hirc.event.get(trigger_id)

                        if event is None:
                            logging.warning(f'Could not find event for trigger '
                                            f'{atl_name} ({trigger_id}) in {f.filename}')
                            continue

                        for ea in event.event_actions:
                            ea = bnk.hirc.event_action.get(ea)
                            if ea is None:
                                logging.warning(f'Event action not found - event:{event.id} action:{ea} '
                                                f'in {f.filename}:{atl_name}')
                                continue

                            sound = bnk.hirc.sound.get(ea.sound_id)
                            if sound is None:
                                # logging.debug(f'Could not locate sound for event_action:{ea.id} sound:{ea.sound_id} '
                                #                 f'in {f.filename}:{atl_name}')
                                continue

                            wem = wems.get(str(sound.wem_id))
                            if wem is None:
                                # logging.warning(f'ERROR: unknown wem_id ({sound.wem_id}) for sound "{sound.id}" '
                                #                 f'in {f.filename}:{atl_name}')
                                continue

                            path = base_path / atl_name / Path(wem.filename).stem
                            if str(path) not in found:
                                item = self._node_cls(path, info=wem)
                                tmp.setdefault(path.parent.as_posix(), []).append(item)
                                found.add(str(path))  # remove duplicates under the same atl_name
            except Exception as e:
                logging.exception(f'Exception processing GameAudio file: {f.filename}', exc_info=e)

        for parent_path, rows in tmp.items():
            if self._should_cancel:
                return  # immediately break
            self.model.appendRowsToPath(parent_path, rows)

        self.scdv.task_finished.emit('load_gameaudio', True, '')
        self.signals.finished.emit()


class SCP4kAudioViewNode(qtg.QStandardItem, ContentItem):
    def __init__(self, path: Path, info=None, *args, **kwargs):
        super().__init__(path.stem, *args, **kwargs)
        ContentItem.__init__(self, path.stem, path)
        self.info = info

    def highlight(self, should_highlight=True):
        if should_highlight:
            self.setBackground(qtc.Qt.darkGray)
        else:
            self.setBackground(qtg.QBrush())

    def contents(self, return_file=False):
        if not self.info:
            return b''

        # generate a free temporary file name
        _ = NamedTemporaryFile(suffix=f'.wem', delete=False)
        tmpout = Path(_.name)
        oggout = Path(tmpout.parent / f'{tmpout.stem}.ogg')
        _.close()

        curdir = os.getcwd()
        try:
            with self.info.archive.open(self.info) as source, tmpout.open('wb') as t:
                shutil.copyfileobj(source, t)
            os.chdir(WW2OGG.parent.absolute())
            check_output(f'{WW2OGG} {tmpout.absolute()} -o {oggout.absolute()} --pcb packed_codebooks_aoTuV_603.bin',
                         stderr=STDOUT, shell=True)
            check_output(f'{REVORB} {oggout}', stderr=STDOUT, shell=True)
            if return_file:
                return oggout
            with oggout.open('rb') as o:
                return o.read()
        except CalledProcessError as e:
            logger.exception(f'Error converting wem "{self.info.filename}": {e}', exc_info=e)
        finally:
            os.chdir(curdir)
            tmpout.unlink(missing_ok=True)
            if not return_file:
                oggout.unlink(missing_ok=True)


class SCAudioViewModel(SCFileViewModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColumnCount(len(SCAUDIOVIEWW_COLUMNS))
        self.setHorizontalHeaderLabels(SCAUDIOVIEWW_COLUMNS)
        self._node_cls = SCP4kAudioViewNode

    def flags(self, index):
        return super().flags(index) & ~qtc.Qt.ItemIsEditable

    def data(self, index, role):
        # if index.column() >= 1 and role == qtc.Qt.DisplayRole:
        #     i = self.itemFromIndex(self.createIndex(index.row(), 0, index.internalId()))
        #     if i is not None:
        #         if index.column() == 1:
        #             return i.type
        #         elif index.column() == 2:
        #             return i.guid
        #         elif index.column() == 3:
        #             return f'{i.guid}:{i.path.as_posix()}'
        return qtg.QStandardItemModel.data(self, index, role)


class AudioViewDock(SCDVSearchableTreeDockWidget):
    __ui_file__ = str(RES_PATH / 'ui' / 'AudioViewDock.ui')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Audio'))
        self.scdv.p4k_loaded.connect(self.handle_p4k_opened)
        self.handle_p4k_opened()  # check if the p4k is opened

        self._currently_playing = None
        self._playlist_index = 0
        self._playlist = []
        self._auto_play = True
        self._audio_buffer = None
        self._audio_tmp = None
        self._media_player = QtMultimedia.QMediaPlayer(self)

        self._media_player.durationChanged.connect(self._handle_duration_changed)
        self._media_player.positionChanged.connect(self._handle_position_changed)
        self._media_player.stateChanged.connect(self._handle_state_changed)

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
        self.durationLabel.setText(seconds_to_str(duration/1000))
        self.playbackSlider.setMaximum(duration)

    def _handle_position_changed(self, position):
        self.positionLabel.setText(seconds_to_str(position/1000))
        self.playbackSlider.setValue(position)

    def _handle_state_changed(self, state):
        if self._currently_playing is not None:
            self._currently_playing.highlight(False)

        if self._playlist:
            self.sc_breadcrumbs.setText(f'{self._playlist_index + 1}/{len(self._playlist)} - '
                                        f'{self._currently_playing.parent().name}_{self._currently_playing.name}')
            self.sc_breadcrumbs.setVisible(True)
        else:
            self.sc_breadcrumbs.setVisible(False)

        if state == QtMultimedia.QMediaPlayer.State.PlayingState:
            self.playButton.hide()
            self.pauseButton.show()
            if self._currently_playing is not None:
                self._currently_playing.highlight(True)
        else:
            self.playButton.show()
            self.pauseButton.hide()

        if state == QtMultimedia.QMediaPlayer.State.StoppedState and self._playlist and self._auto_play:
            self.play_next()

    def _change_media(self, item):
        """ Returns the item if set correctly, else None """
        if item.info is None:
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
        self._audio_tmp = item.contents(return_file=True)
        self._media_player.setMedia(qtc.QUrl.fromLocalFile(str(self._audio_tmp.absolute())))
        self._currently_playing = item

    def set_volume(self, level):
        self._media_player.setVolume(level)
        self.volumeDial.setValue(level)

    def play(self, item=None):
        if item is None:
            if not self._currently_playing:
                return
            item = self._currently_playing
        elif item.info is None:
            return

        if self._playlist:
            self._auto_play = True

        if item != self._currently_playing:
            self._change_media(item)
        if item == self._currently_playing:
            self.sc_tree.expand(self.proxy_model.mapFromSource(item.index()))
            self.sc_tree.scrollTo(self.proxy_model.mapFromSource(item.index()))
            self._media_player.play()

    def pause(self):
        self._media_player.pause()

    def play_previous(self):
        # if a playlist and in the first two seconds, play the previous track in the playlist
        self.stop()
        # self._media_player.position() always returns 0, so use the playbackSlider value which is updated
        if self._playlist and self.playbackSlider.value() < 2000:
            try:
                self._playlist_index = max(0, self._playlist.index(self._currently_playing) - 1)
            except ValueError:
                self._playlist_index = 0
            if self._playlist_index <= len(self._playlist):
                self.play(self._playlist[self._playlist_index])
        else:
            # just play the same sound again if not playlist
            self._media_player.play()

    def stop(self):
        self._auto_play = False
        self._media_player.stop()

    def play_next(self):
        self.stop()
        if self._playlist:
            try:
                self._playlist_index = self._playlist.index(self._currently_playing) + 1
            except ValueError:
                self._playlist_index = 0
            if self._playlist_index < len(self._playlist):
                self.play(self._playlist[self._playlist_index])
            else:
                self._playlist_index = len(self._playlist)-1

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
        if item.info:
            if item in self._playlist:
                self._playlist_index = self._playlist.index(item)
            else:
                self._playlist = []
            self.play(item)
        else:
            self._currently_playing = None
            self._playlist = [item for item in self.get_selected_items() if item.info is not None]
            self.play_next()

    @Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = [_ for _ in self.get_selected_items() if _.info is not None]

        # Item Actions
        if not selected_items:
            return

        if action == 'extract':
            edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Extract to...')
            if edir:
                total = len(selected_items)
                self.scdv.task_started.emit('extract_audio', f'Extracting Game Audio to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    self.scdv.update_status_progress.emit('extract_audio', 1, 0, total, f'Extracting {item.name} to {edir}')
                    try:
                        outfile = Path(edir) / item.parent().parent().name / f'{item.parent().name}_{item.name}.ogg'
                        outfile.parent.mkdir(parents=True, exist_ok=True)
                        tmp = item.contents(return_file=True)
                        shutil.move(tmp, outfile)
                    except Exception as e:
                        print(e)

                self.scdv.task_finished.emit('extract_audio', True, '')
                show_file_in_filemanager(Path(edir))
