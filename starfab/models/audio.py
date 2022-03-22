import time
from functools import cached_property
from pathlib import Path

from starfab import get_starfab
from starfab.gui import qtc, qtw, qtg
from starfab.gui.utils import icon_provider
from starfab.models.common import (
    PathArchiveTreeSortFilterProxyModel,
    PathArchiveTreeModelLoader,
    PathArchiveTreeItem,
    ContentItem,
    ThreadLoadedPathArchiveTreeModel,
)
from starfab.settings import get_ww2ogg, get_revorb

SCAUDIOVIEWW_COLUMNS = ["Name"]
GAME_AUDIO_P4K_RELPATH = Path("Data/Libs/")
GAME_AUDIO_P4K_SEARCH = str(GAME_AUDIO_P4K_RELPATH / "GameAudio" / "*.xml")
GAME_AUDIO_DCB_SEARCH = "libs/foundry/records/musiclogic/*"


class AudioTreeSortFilterProxyModel(PathArchiveTreeSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if not self._filter and not self.additional_filters:
            return True

        if parent := source_parent.internalPointer():
            try:
                item = parent.children[source_row]
            except IndexError:
                return False
            if not self._filter and not self.checkAdditionFilters(item):
                return False
            elif self.checkAdditionFilters(item):
                if self.filterCaseSensitivity() == qtc.Qt.CaseInsensitive:
                    return (
                        self._filter.lower() in item.name.lower()
                        or self._filter.lower() in item.wems
                    )
                else:
                    return self._filter in item._path or self._filter in item.wems
        return False


class AudioTreeLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        ga_files = self.starfab.sc.p4k.search(GAME_AUDIO_P4K_SEARCH)
        self.starfab.task_started.emit(
            "init_gameaudio", "Initializing Game Audio", 0, len(ga_files)
        )

        t = time.time()
        wwise = self.model.archive.wwise
        wwise.ww2ogg = Path(get_ww2ogg())
        wwise.revorb = Path(get_revorb())

        for i, p4kfile in enumerate(ga_files):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.starfab.update_status_progress.emit("init_gameaudio", i, 0, 0, "")
                t = time.time()
            wwise.load_game_audio_file(self.starfab.sc.p4k.open(p4kfile))

        self.starfab.task_finished.emit("init_gameaudio", True, "")
        return wwise.preloads

    def load_item(self, item):
        base_path = "GameAudio" + "/" + item
        preload = self.model.archive.wwise.preloads[item]
        atl_names = list(preload["triggers"].keys()) + list(
            preload["external_sources"].keys()
        )
        for atl_name in atl_names:
            self._item_cls(
                base_path + "/" + atl_name,
                model=self.model,
                atl_name=atl_name,
                parent=self.model.parentForPath(base_path),
            )


class AudioTreeItem(PathArchiveTreeItem, ContentItem):
    _cached_properties_ = PathArchiveTreeItem._cached_properties_ + ["wems"]

    def __init__(self, path, model, atl_name=None, parent=None):
        super().__init__(path, model, parent)
        self.atl_name = atl_name
        self._background = qtg.QBrush()
        self._wems = []
        self._wems_loaded = False

    @cached_property
    def icon(self):
        if self.children:
            return icon_provider.icon(icon_provider.Folder)
        return icon_provider.icon(icon_provider.File)

    @property
    def wems(self):
        if self.atl_name and not self._wems_loaded:
            self._wems = list(
                get_starfab().sc.wwise.wems_for_atl_name(self.atl_name).keys()
            )
            self._wems_loaded = True
        return self._wems

    def highlight(self, should_highlight=True):
        if should_highlight:
            self._background = qtg.QPalette().highlight()
        else:
            self._background = qtg.QBrush()

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.name
            elif column == 1:
                return self.type
            elif column == 2:
                return self.guid
            else:
                return ""
        elif role == qtc.Qt.BackgroundRole:
            return self._background
        return super().data(column, role)


class AudioTreeModel(ThreadLoadedPathArchiveTreeModel):
    def __init__(self, sc_manager):
        self._sc_manager = sc_manager
        super().__init__(
            archive=None,
            columns=SCAUDIOVIEWW_COLUMNS,
            item_cls=AudioTreeItem,
            parent=sc_manager,
            loader_cls=AudioTreeLoader,
            loader_task_name="load_audio_model",
            loader_task_status_msg="Processing Audio",
        )

        self._sc_manager.p4k_model.loaded.connect(self._on_p4k_loaded)
        self._sc_manager.p4k_model.unloading.connect(
            self._on_p4k_unloading, qtc.Qt.BlockingQueuedConnection
        )

    @qtc.Slot()
    def _on_p4k_loaded(self):
        self.load(self._sc_manager.sc)

    @qtc.Slot()
    def _on_p4k_unloading(self):
        self.unload()
