import io
import time
import typing
import logging
import operator
from pathlib import Path
from datetime import timedelta
from functools import cached_property

from scdatatools.p4k import P4KInfo

from starfab import get_starfab
from starfab.gui import qtc, qtw
from starfab.log import getLogger
from starfab.utils import show_file_in_filemanager
from starfab.gui.utils import icon_provider, icon_for_path

logger = getLogger(__name__)


class AudioConverter(qtc.QRunnable):
    def __init__(self, wem_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = BackgroundRunnerSignals()
        self.wem_id = wem_id

    def run(self):
        try:
            starfab = get_starfab()
            oggfile = starfab.sc.wwise.convert_wem(self.wem_id, return_file=True)
            result = {"id": self.wem_id, "ogg": oggfile, "msg": ""}
        except Exception as e:
            msg = f"AudioConverter failed to convert wem {self.wem_id}: {repr(e)}"
            logger.exception(msg, exc_info=e)
            result = {"id": self.wem_id, "ogg": None, "msg": msg}
        self.signals.finished.emit(result)
        return result


class ExportRunner(qtc.QRunnable):
    def __init__(
        self,
        p4k_files: typing.List[P4KInfo],
        outdir: typing.Union[Path, str],
        save_to: bool = False,
        export_options: typing.Dict = None,
    ):
        super().__init__()
        self.signals = BackgroundRunnerSignals()
        self.starfab = get_starfab()
        self.p4k_files = p4k_files
        self.outdir = outdir
        self.save_to = save_to
        self.export_options = export_options

    def run(self) -> None:
        logger.debug(f"Exporting {len(self.p4k_files)} file[s] to {self.outdir}")
        logger.debug(f"{self.export_options}")

        task_id = f"export_runner_{hash(self)}"
        self.starfab.task_started.emit(
            task_id, f"Extracting to {self.outdir}", 0, len(self.p4k_files)
        )

        def _monitor(msg, progress=None, total=None, level=logging.INFO, exc_info=None):
            logger.log(level, msg)
            self.starfab.update_status_progress.emit(task_id, progress, 0, total, "")

        try:
            self.starfab.sc_manager.sc.p4k.extractall(
                members=self.p4k_files,
                path=self.outdir,
                monitor=_monitor,
                save_to=self.save_to,
                overwrite=self.export_options.get("overwrite", False),
                converters=self.export_options.get("converters", []),
                converter_options=self.export_options,
            )
        except Exception as e:
            logger.exception(f"Export failed", exc_info=e)
            self.signals.finished.emit({"error": str(e)})
            self.starfab.task_finished.emit(task_id, False, f"Error during export: {e}")
        else:
            self.signals.finished.emit({"error": ""})
            show_file_in_filemanager(Path(self.outdir).absolute())
            self.starfab.task_finished.emit(task_id, True, "")


class BackgroundRunnerSignals(qtc.QObject):
    cancel = qtc.Signal()
    finished = qtc.Signal(dict)


class PathArchiveTreeSortFilterProxyModel(qtc.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter = ""
        self._filters = []
        self._dynamic_filters = []
        self.setRecursiveFilteringEnabled(True)

    @property
    def additional_filters(self):
        return self._filters + self._dynamic_filters

    def setFilterText(self, text):
        self._filter = text
        self.invalidateFilter()

    def setAdditionFilters(self, filters):
        self._dynamic_filters = filters
        self.invalidateFilter()

    def checkAdditionFilters(self, item):
        accepted = True
        for op, adfilt in self.additional_filters:
            if op == operator.not_:
                accepted = op(adfilt(item))
            else:
                accepted = op(accepted, adfilt(item))
        return accepted

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
                    return self._filter.lower() in item._path.lower()
                else:
                    return self._filter in item._path
        return False


class PathArchiveTreeItem:
    _cached_properties_ = ["info", "icon", "suffix", "path"]

    def __init__(self, path, model, parent=None):
        self._path = path
        self.name = path.rsplit("/", maxsplit=1)[-1]
        self.model = model
        self.parent = parent
        self.children = []
        self.children_by_name = {}

        if parent is not None:
            parent.appendChild(self)

    def __repr__(self):
        return f"<PathArchiveTreeItem {self.path} children:{len(self.children)}>"

    def clear_cache(self):
        """Clear cached property values, triggering them to be recalculated"""
        for c in self._cached_properties_:
            if c in self.__dict__:
                del self.__dict__[c]

    @property
    def archive(self):
        return self.model.archive

    @cached_property
    def path(self):
        return Path(self._path)

    @cached_property
    def info(self):
        return None

    @cached_property
    def suffix(self):
        if "." in self.name:
            return "." + self.name.split(".", maxsplit=1)[-1]
        return ""

    @cached_property
    def icon(self):
        return icon_for_path(self.name) or icon_provider.icon(icon_provider.Folder)

    def appendChild(self, child):
        child.parent = self
        self.children.append(child)
        self.children_by_name[child.name] = child

    def appendChildren(self, children):
        for child in children:
            self.appendChild(child)

    def child(self, row):
        return self.children[row]

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def index(self):
        return self.model.createIndex(self.row(), 0, self)

    def childCount(self):
        return len(self.children)

    def parentItem(self):
        return self.parent

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.name
            elif column == 1:
                return self.suffix
            return ""
        elif role == qtc.Qt.DecorationRole:
            if column == 0:
                return self.icon
        return None


class PathArchiveTreeModel(qtc.QAbstractItemModel):
    def __init__(self, archive, columns=None, item_cls=None, parent=None):
        super().__init__(parent=parent)
        self.archive = archive
        self.columns = columns or ["Name", "Type"]
        self._item_cls = item_cls or PathArchiveTreeItem
        self.root_item = None
        self._parent_cache = {".": self.root_item}
        self._setup_root()

    def _setup_root(self):
        self.root_item = self._item_cls("root", model=self)

    def clear(self):
        self.archive = None
        self._setup_root()
        self._parent_cache = {".": self.root_item}

    def index(self, row, column, parent=None):
        if not self.hasIndex(row, column, parent):
            return qtc.QModelIndex()

        if not parent.isValid():
            parent = self.root_item
        else:
            parent = parent.internalPointer()

        if child := parent.child(row):
            return self.createIndex(row, column, child)
        return qtc.QModelIndex()

    def parent(self, index: qtc.QModelIndex):
        if not index.isValid():
            return qtc.QModelIndex()

        child = index.internalPointer()
        parent = child.parent
        if parent == self.root_item or parent is None:
            return qtc.QModelIndex()
        return self.createIndex(parent.row(), 0, parent)

    def rowCount(self, parent: qtc.QModelIndex):
        if parent.column() > 0:
            return 0

        parent = self.root_item if not parent.isValid() else parent.internalPointer()
        return parent.childCount()

    def columnCount(self, parent: qtc.QModelIndex) -> int:
        return len(self.columns)

    def headerData(self, section: int, orientation: qtc.Qt.Orientation, role: int):
        if orientation == qtc.Qt.Horizontal and role == qtc.Qt.DisplayRole:
            return self.columns[section]
        return None

    def data(self, index: qtc.QModelIndex, role: int):
        if not index.isValid():
            return None

        item = index.internalPointer()
        return item.data(index.column(), role)

    def flags(self, index):
        if not index.isValid():
            return qtc.Qt.NoItemFlags
        return super().flags(index)

    def parentForPath(self, path):
        if not path:
            return self.root_item
        parent_path, name = path.rsplit("/", maxsplit=1) if "/" in path else ("", path)
        if "." in name:
            return self.parentForPath(parent_path)
        lower_path = path.lower()
        if lower_path not in self._parent_cache:
            parent = self.parentForPath(parent_path)
            self._parent_cache[lower_path] = self._item_cls(
                path, model=self, parent=parent
            )
        return self._parent_cache[lower_path]

    def indexForPath(self, path):
        if (item := self.itemForPath(path)) is not None:
            return self.createIndex(item.parent.children.index(item), 0, item)
        return qtc.QModelIndex()

    def itemForPath(self, path):
        if isinstance(path, Path):
            path = path.as_posix()
        if "/" in path:
            parent_path, name = (
                path.rsplit("/", maxsplit=1) if "/" in path else ("", path)
            )
            if parent := self._parent_cache.get(parent_path.lower()):
                return parent.children_by_name.get(name)
        return self._parent_cache.get(path.lower())

    def appendChildrenToPath(self, path, rows):
        if parent := self.parentForPath(path):
            parent.appendChildren(rows)


class PathArchiveTreeModelLoader(qtc.QRunnable):
    def __init__(
        self,
        model,
        item_cls,
        task_name="",
        task_status_msg="",
        load_limit=-1,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        logger.debug(f"Created loader for {model} {task_name}")
        self.starfab = get_starfab()
        self.model = model
        self.signals = BackgroundRunnerSignals()
        self._item_cls = item_cls or PathArchiveTreeItem
        self._should_cancel = False
        self._load_limit = load_limit  # This is for dev/debugging purposes
        self.task_name = task_name or self.__class__.__name__
        self.task_status_message = task_status_msg
        self.signals.cancel.connect(
            self._handle_cancel, qtc.Qt.BlockingQueuedConnection
        )
        self.setAutoDelete(True)

    def _handle_cancel(self):
        self._should_cancel = True

    def items_to_load(self):
        return []

    def load_item(self, item):
        self._item_cls(item, model=self.model, parent=self.model.parentForPath(item))

    def run(self):
        logger.debug(f"Starting to load {self.task_name}")
        start_time = time.time()

        if self.task_status_message:
            self.starfab.task_started.emit(
                self.task_name, self.task_status_message, 0, 1
            )

        items = self.items_to_load()

        if self.task_status_message:
            self.starfab.update_status_progress.emit(
                self.task_name, 0, 0, len(items), ""
            )

        t = time.time()
        for i, f in enumerate(items):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                if self.task_status_message:
                    self.starfab.update_status_progress.emit(
                        self.task_name, i, 0, 0, ""
                    )
                t = time.time()

            if 0 <= self._load_limit < i:
                break

            self.load_item(f)

        logger.debug(
            f"Loaded {self.task_name} in {timedelta(seconds=time.time() - start_time)}"
        )
        if self.task_status_message:
            self.starfab.task_finished.emit(self.task_name, True, "")
        self.signals.finished.emit({})


class ContentItem:
    def __init__(self, name, path, contents=None):
        if contents is not None:
            if isinstance(contents, io.BytesIO):
                self._contents = contents
            elif isinstance(contents, str):
                self._contents = io.BytesIO(contents.encode("utf-8"))
            else:
                self._contents = io.BytesIO(contents)
        else:
            self._contents = io.BytesIO()
        self.name = name
        self.path = path

    def contents(self):
        return self._contents


class CheckableModelWrapper(PathArchiveTreeModel):
    def __init__(self, model: PathArchiveTreeModel, checkbox_column=0, parent=None):
        qtc.QAbstractItemModel.__init__(self, parent)
        self.archive = model.archive
        self.columns = model.columns or ["Name"]
        self.checkbox_column = checkbox_column
        self._item_cls = model._item_cls
        self._checked = {}
        self._model = model

    def _sync_checked(self, item, value, index):
        self._checked[item] = value
        self.dataChanged.emit(index, index, [qtc.Qt.EditRole])
        for i, child in enumerate(item.children):
            self._sync_checked(child, value, self.createIndex(i, 0, child))

    def select_all(self):
        for i, item in enumerate(self.root_item.children):
            self._sync_checked(item, qtc.Qt.Checked, self.createIndex(i, 0, item))

    def deselect_all(self):
        for i, item in enumerate(self.root_item.children):
            self._sync_checked(item, qtc.Qt.Unchecked, self.createIndex(i, 0, item))

    @property
    def checked_items(self):
        return [i for i, checked in self._checked.items() if checked]

    @property
    def root_item(self):
        return self._model.root_item

    @property
    def _parent_cache(self):
        return self._model._parent_cache

    def flags(self, index):
        if not index.isValid():
            return qtc.Qt.NoItemFlags
        return super().flags(index) | qtc.Qt.ItemIsUserCheckable

    def _update_parent(self, item):
        if item == self.root_item:
            return

        state = qtc.Qt.Unchecked
        all = True
        for child in item.children:
            if (cstate := self._checked.get(child, qtc.Qt.Unchecked)) != qtc.Qt.Checked:
                all = False
            if cstate > qtc.Qt.Unchecked:
                state = qtc.Qt.PartiallyChecked
        if all:
            state = qtc.Qt.Checked
        self._checked[item] = state
        index = self.createIndex(item.parent.children.index(item), 0, item)
        self.dataChanged.emit(index, index, [qtc.Qt.EditRole])
        self._update_parent(item.parent)

    def setData(self, index, value, role=qtc.Qt.EditRole):
        if role == qtc.Qt.CheckStateRole and index.column() == self.checkbox_column:
            item = index.internalPointer()
            self._sync_checked(
                item, qtc.Qt.Checked if value else qtc.Qt.Unchecked, index
            )
            self._update_parent(item.parent)
        return True

    def data(self, index: qtc.QModelIndex, role: int):
        if role == qtc.Qt.CheckStateRole:
            item = index.internalPointer()
            return self._checked.get(item, qtc.Qt.Unchecked)
        return super().data(index, role)


class ThreadLoadedPathArchiveTreeModel(PathArchiveTreeModel):
    loaded = qtc.Signal()
    unloading = qtc.Signal()
    cancel_loading = qtc.Signal()

    def __init__(
        self,
        archive=None,
        columns=None,
        item_cls=None,
        parent=None,
        loader_cls=PathArchiveTreeModelLoader,
        loader_task_name="",
        loader_task_status_msg="",
    ):
        super().__init__(
            archive=archive, columns=columns, item_cls=item_cls, parent=parent
        )
        self.is_loaded = False
        self._loader = None
        self._loader_cls = loader_cls
        self.loader_task_name = loader_task_name
        self.loader_task_status_msg = loader_task_status_msg

    def unload(self):
        if self._loader is not None:
            self._loader.signals.cancel.emit()
        self.clear()

    def _loaded(self):
        self.is_loaded = True
        self.loaded.emit()

    def load(self, archive, task_name="", task_status_msg=""):
        if self.is_loaded:
            self.unload()

        task_name = task_name or self.loader_task_name
        task_status_msg = task_status_msg or self.loader_task_status_msg

        logger.debug(f"Loading {self.__class__.__name__} model")

        self.archive = archive
        self._loader = self._loader_cls(
            self,
            item_cls=self._item_cls,
            task_name=task_name,
            task_status_msg=task_status_msg,
        )
        self._loader.signals.finished.connect(self._loaded)
        qtc.QThreadPool.globalInstance().start(self._loader)
