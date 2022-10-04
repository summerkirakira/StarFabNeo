import os
import shutil
import time
from functools import partial
from pathlib import Path

import qtawesome as qta
from qtpy import QtMultimedia
from qtpy.QtCore import Signal, Slot

from starfab.gui import qtc, qtw, qtg
from starfab.gui.utils import ScrollMessageBox, seconds_to_str
from starfab.gui.widgets.dock_widgets.common import StarFabSearchableTreeWidget
from starfab.log import getLogger
from starfab.models.audio import (
    SCAUDIOVIEWW_COLUMNS,
    AudioTreeSortFilterProxyModel,
    AudioTreeModel,
    AudioTreeLoader,
    AudioTreeItem,
)
from starfab.models.common import AudioConverter
from starfab.resources import RES_PATH
from starfab.utils import show_file_in_filemanager

logger = getLogger(__name__)


class _AudioCleanup(qtc.QRunnable):
    def __init__(self, ogg_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ogg_path = ogg_path

    def run(self):
        time.sleep(0.5)  # makes sure it's unloaded from media_player
        Path(self.ogg_path).unlink(missing_ok=True)


class AudioTreeWidget(StarFabSearchableTreeWidget):
    __ui_file__ = str(RES_PATH / "ui" / "AudioTreeWidget.ui")

    audio_conversion_complete = Signal(str, Path, str)
    play_wem = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=AudioTreeSortFilterProxyModel, *args, **kwargs)
        self.starfab.sc_manager.audio_model.loaded.connect(self.handle_audio_loaded)
        self.handle_audio_loaded()  # check if the p4k is opened

        self.play_wem.connect(self._handle_play_wem)

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
        self._media_player.playbackStateChanged.connect(self._handle_state_changed)

        self.audio_conversion_complete.connect(self._handle_audio_conversion)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setSizes([1024, 50])
        self.wem_list.hide()

        # self.wem_list.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        # self.wem_list.customContextMenuRequested.connect(self._show_ctx_menu)
        self.wem_list.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.wem_list.doubleClicked.connect(self._on_wem_doubleclick)

        self.playButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaPlay))
        self.playButton.clicked.connect(
            lambda b: self.play()
        )  # lambda consumes the checked bool
        self.pauseButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaPause))
        self.pauseButton.clicked.connect(self.pause)
        self.pauseButton.hide()
        self.prevButton.setIcon(
            self.style().standardIcon(qtw.QStyle.SP_MediaSkipBackward)
        )
        self.prevButton.clicked.connect(self.play_previous)
        self.stopButton.setIcon(self.style().standardIcon(qtw.QStyle.SP_MediaStop))
        self.stopButton.clicked.connect(self.stop)
        self.nextButton.setIcon(
            self.style().standardIcon(qtw.QStyle.SP_MediaSkipForward)
        )
        self.nextButton.clicked.connect(self.play_next)

        self.sc_breadcrumbs.setVisible(True)
        self.gotoButton.clicked.connect(self._handle_goto)
        self.gotoButton.setIcon(qta.icon("mdi.arrow-right-thin-circle-outline"))
        self.play_info.setVisible(False)

        # self.playbackSlider.sliderPressed.connect(self._handle_playback_pressed)
        self.playbackSlider.sliderReleased.connect(self._handle_playback_released)
        # TODO: handle saving the volume setting in the settings
        self.volumeDial.sliderMoved.connect(self.set_volume)
        self.set_volume(75)

        self.ctx_manager.default_menu.addSeparator()
        extract = self.ctx_manager.default_menu.addAction("Extract to...")
        extract.triggered.connect(partial(self.ctx_manager.handle_action, "extract"))
        extract = self.ctx_manager.menus[""].addAction("Extract to...")
        extract.triggered.connect(partial(self.ctx_manager.handle_action, "extract"))

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
            wem_txt = f" [{self._currently_playing_wem_id + 1}/{len(self._currently_playing.wems)}]"
        else:
            wem_txt = ""
        if self._playlist:
            self.sc_breadcrumbs.setText(
                f"{playlist_index + 1}/{len(self._playlist)} - "
                f"{self._currently_playing.name}{wem_txt}"
            )
        else:
            self.sc_breadcrumbs.setText(f"{self._currently_playing.name}{wem_txt}")

        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.hide()
            self.pauseButton.show()
            if self._currently_playing is not None:
                self._currently_playing.highlight(True)
            if self._currently_playing_wem_id is not None:
                self._highlight_wem(self._currently_playing_wem_id, True)
        else:
            self.playButton.show()
            self.pauseButton.hide()

        if (
            state == QtMultimedia.QMediaPlayer.PlaybackState.StoppedState
            and self._playlist
            and self._auto_play
        ):
            self.play_next()

    def _handle_goto(self):
        if self._currently_playing:
            tree_item = self.proxy_model.mapFromSource(self._currently_playing.index())
            self.sc_tree.expand(tree_item)
            self.sc_tree.scrollTo(tree_item)

    def _change_media(self, item, wem_index):
        """Returns the item if set correctly, else None"""
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
            self._media_player.setSource(qtc.QUrl())
            qtc.QThreadPool.globalInstance().start(_AudioCleanup(self._audio_tmp))
            self._audio_tmp = None

        try:
            conv = AudioConverter(item.wems[wem_index])
            conv.signals.finished.connect(self._handle_audio_conversion)
            qtc.QThreadPool.globalInstance().start(conv)
            # self._audio_tmp = self.starfab.sc.wwise.convert_wem(item.wems[wem_index], return_file=True)
            self._currently_playing = item
            self._currently_playing_wem_id = wem_index
            # self._media_player.setMedia(qtc.QUrl.fromLocalFile(str(self._audio_tmp.absolute())))
        except Exception as e:
            ScrollMessageBox.critical(
                self, "Audio", f"Cannot play {item.atl_name}: {repr(e)}"
            )
            self._currently_playing = None
            self._currently_playing_wem_id = None

    def _handle_play_wem(self, wem_id, item=None):
        """Allows for the playing of a wem from an item, or directly from the p4k"""
        self.stop()
        if item is None:
            # TODO: _fake_item is a hacky hack hack way of just "getting it in", should be fixed
            item = AudioTreeItem(
                path=str(wem_id), model=self.sc_tree_model, atl_name=str(wem_id)
            )
            item._wems = [wem_id]
            item._wems_loaded = True
        self._playlist = []
        self.play(item, item.wems.index(wem_id))

    @Slot(str, Path)
    def _handle_audio_conversion(self, conv_result):
        wem_id = conv_result.get("id")
        ogg_path = conv_result.get("ogg")
        error_msg = conv_result.get("msg")
        if error_msg:
            ScrollMessageBox.critical(self, "Audio", error_msg)
            self._currently_playing = None
            self._currently_playing_wem_id = None
        elif (
            self._currently_playing is not None
            and self._currently_playing_wem_id is not None
            and self._currently_playing.wems[self._currently_playing_wem_id] == wem_id
        ):
            self._audio_tmp = ogg_path
            self._media_player.setSource(
                qtc.QUrl.fromLocalFile(str(self._audio_tmp.absolute()))
            )
            wem_item = self.wem_list.item(self._currently_playing_wem_id)
            self.wem_list.scrollToItem(wem_item)
            self._media_player.play()
        elif ogg_path:
            # we must have started playing a new song, unlink this file
            os.unlink(ogg_path)

    def set_volume(self, level):
        if (ao := self._media_player.audioOutput()) is None:
            ao = QtMultimedia.QAudioOutput()
            self._media_player.setAudioOutput(ao)
        ao.setVolume(level)
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
        else:
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
                    playlist_index = max(
                        0, self._playlist.index(self._currently_playing) - 1
                    )
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

    def handle_audio_loaded(self):
        if self.starfab.sc_manager.audio_model.is_loaded:
            self.sc_tree_model = self.starfab.sc_manager.audio_model
            self.proxy_model.setSourceModel(self.sc_tree_model)
            self.sc_tree.setModel(self.proxy_model)
            self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
            header = self.sc_tree.header()
            header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)

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
            self._playlist = [
                item for item in self.get_selected_items() if item.atl_name is not None
            ]
            self.play_next()

    @Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = [
            _ for _ in self.get_selected_items() if _.atl_name is not None
        ]

        # Item Actions
        if not selected_items:
            return

        if action == "extract":
            edir = qtw.QFileDialog.getExistingDirectory(self.starfab, "Extract to...")
            if edir:
                total = len(selected_items)
                self.starfab.task_started.emit(
                    "extract_audio", f"Extracting Game Audio to {edir}", 0, total
                )
                for i, item in enumerate(selected_items):
                    self.starfab.update_status_progress.emit(
                        "extract_audio",
                        1,
                        0,
                        total,
                        f"Extracting {item.name} to {edir}",
                    )
                    base_out = Path(edir) / item.parent.name
                    for wem in item.wems:
                        try:
                            outfile = base_out / f"{item.atl_name}_{wem}.ogg"
                            outfile.parent.mkdir(parents=True, exist_ok=True)
                            tmp = self.starfab.sc.wwise.convert_wem(
                                wem, return_file=True
                            )
                            shutil.move(tmp, outfile)
                        except Exception as e:
                            logger.exception(
                                f"Exception extracting wem {item.atl_name}.{wem}",
                                exc_info=e,
                            )

                self.starfab.task_finished.emit("extract_audio", True, "")
                show_file_in_filemanager(Path(edir))

    def _on_wem_doubleclick(self, index):
        if self._currently_playing:
            self.stop()
            if self._currently_playing in self._playlist:
                self._playlist_index = (
                    self._playlist.index(self._currently_playing),
                    index.row(),
                )
            else:
                self._playlist = []
            self.play(self._currently_playing, index.row())

    def _highlight_wem(self, row, should_highlight):
        item = self.wem_list.item(row)
        if item is not None:
            if should_highlight:
                item.setBackground(qtg.QPalette().highlight())
            else:
                item.setBackground(qtg.QBrush())
