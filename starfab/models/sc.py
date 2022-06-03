import time
import typing
from pathlib import Path

import sentry_sdk

from scdatatools.sc import StarCitizen
from scdatatools.utils import log_time
from starfab.gui import qtc
from starfab.log import getLogger
from .audio import AudioTreeModel
from .datacore import DCBModel
from .localization import LocalizationModel
from .p4k import P4KModel
from .tag_database import TagDatabaseModel

logger = getLogger(__name__)


class _LoaderSignals(qtc.QObject):
    started = qtc.Signal()
    finished = qtc.Signal()

    task_started = qtc.Signal(str, str, int, int)
    update_status_progress = qtc.Signal(str, int, int, int, str)
    task_finished = qtc.Signal(str, bool, str)


class _SCLoader(qtc.QRunnable):
    def __init__(self, sc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = _LoaderSignals()
        self.sc = sc

    def run(self):
        with log_time(
            f"Loading {self.sc.game_folder} ({self.sc.version_label})", logger.info
        ):
            t = time.time()

            def p4k_load_monitor(msg, progress, total):
                nonlocal t
                if (time.time() - t) > 1:
                    self.signals.update_status_progress.emit(
                        "load_p4k",
                        progress / 1024 // 1024,
                        None,
                        total / 1024 // 1024,
                        None,
                    )
                    t = time.time()

            with log_time("Loading P4K", logger.debug):
                self.signals.task_started.emit("load_p4k", "Loading P4K", 0, 1)
                self.sc._p4k_load_monitor = p4k_load_monitor
                assert self.sc.p4k is not None
                self.signals.task_finished.emit("load_p4k", True, "")

            self.signals.finished.emit()


class StarCitizenManager(qtc.QObject):
    preparing_to_load = qtc.Signal(str)
    preparing_to_unload = qtc.Signal()
    loaded = qtc.Signal()
    unloaded = qtc.Signal()
    load_failed = qtc.Signal(str, object)

    opened = qtc.Signal()
    unload = qtc.Signal()
    load_sc = qtc.Signal(str)

    def __init__(self, starfab):
        super().__init__(parent=starfab)
        self._starfab = starfab
        self.sc = None

        sentry_sdk.set_context("sc", {})
        sentry_sdk.set_tag('sc.version', None)
        sentry_sdk.set_tag('sc.mode', None)

        self.unload.connect(self._unload)
        self.load_sc.connect(self._load_sc)

        self.p4k_model = P4KModel(self)
        self.datacore_model = DCBModel(self)

        self.localization_model = LocalizationModel(self)
        self.tag_database_model = TagDatabaseModel(self)
        self.audio_model = AudioTreeModel(self)

    @qtc.Slot()
    def _unload(self):
        """Unload the currently loaded StarCitizen"""
        logger.debug(f"Unloading {self.sc.game_folder}")
        if self.sc is not None:
            self.preparing_to_unload.emit()
        self.p4k_model.unload()
        self.datacore_model.unload()
        sentry_sdk.set_context("sc", {})
        sentry_sdk.set_tag('sc.version', None)
        sentry_sdk.set_tag('sc.mode', None)
        self.unloaded.emit()
        del self.sc
        self.sc = None

    @qtc.Slot()
    def _loaded(self):
        self.loaded.emit()
        self.p4k_model.load(self.sc.p4k)
        self.datacore_model.load(
            self.sc
        )  # datacore loader expects the StarCitizen object

    @qtc.Slot(str)
    def _load_sc(self, game_folder: typing.Union[str, Path], p4k_file="Data.p4k"):
        if self.sc is not None:
            self._unload()

        logger.debug(f"Opening {game_folder}")
        try:
            self.sc = StarCitizen(game_folder, p4k_file)
        except Exception as e:
            self.load_failed.emit(str(e), e)
            return

        sc_dir = self.sc.p4k_file.parent.name
        mode = sc_dir if sc_dir in ['LIVE', 'PTU'] else 'unknown'
        sentry_sdk.set_context("sc", {
            "version": self.sc.version,
            "version_label": self.sc.version_label,
            "mode": mode
        })
        sentry_sdk.set_tag('sc.version', self.sc.version_label)
        sentry_sdk.set_tag('sc.mode', mode)

        self.preparing_to_load.emit(self.sc.game_folder)
        loader = _SCLoader(self.sc)

        loader.signals.task_started.connect(self._starfab.task_started)
        loader.signals.task_finished.connect(self._starfab.task_finished)
        loader.signals.update_status_progress.connect(
            self._starfab.update_status_progress
        )
        loader.signals.finished.connect(self._loaded)

        qtc.QThreadPool.globalInstance().start(loader)
        self.opened.emit()
