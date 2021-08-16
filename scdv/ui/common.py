import io
import time
import logging
import typing
from pathlib import Path
from datetime import timedelta
from functools import cached_property

from scdv import get_scdv
from scdv.ui import qtc
from scdv.ui.utils import icon_provider, icon_for_path

logger = logging.getLogger(__name__)


class AudioConverter(qtc.QRunnable):
    def __init__(self, wem_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = BackgroundRunnerSignals()
        self.wem_id = wem_id

    def run(self):
        try:
            scdv = get_scdv()
            oggfile = scdv.sc.wwise.convert_wem(self.wem_id, return_file=True)
            result = {'id': self.wem_id, 'ogg': oggfile, 'msg': ''}
        except Exception as e:
            msg = f'AudioConverter failed to convert wem {self.wem_id}: {repr(e)}'
            logger.exception(msg, exc_info=e)
            result = {'id': self.wem_id, 'ogg': None, 'msg': msg}
        self.signals.finished.emit(result)
        return result


class BackgroundRunnerSignals(qtc.QObject):
    cancel = qtc.Signal()
    finished = qtc.Signal(dict)


class PathArchiveTreeSortFilterProxyModel(qtc.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filter = ''
        self.additional_filters = []

    def setFilterText(self, text):
        self._filter = text
        self.invalidateFilter()

    def setAdditionFilters(self, filters):
        self.additional_filters = filters
        self.invalidateFilter()

    def checkAdditionFilters(self, item):
        accepted = True
        for op, adfilt in self.additional_filters:
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
    _cached_properties_ = ['info', 'icon', 'suffix', 'path']

    def __init__(self, path, model, parent=None):
        self._path = path
        self.name = path.rsplit('/', maxsplit=1)[-1]
        self.model = model
        self.parent = parent
        self.children = []
        self.children_by_name = {}

        if parent is not None:
            parent.appendChild(self)

    def __repr__(self):
        return f'<PathArchiveTreeItem {self.path} children:{len(self.children)}>'

    def clear_cache(self):
        """ Clear cached property values, triggering them to be recalculated """
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
        if '.' in self.name:
            return '.' + self.name.split('.', maxsplit=1)[-1]
        return ''

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
            return ''
        elif role == qtc.Qt.DecorationRole:
            if column == 0:
                return self.icon
        return None


class PathArchiveTreeModel(qtc.QAbstractItemModel):
    def __init__(self, archive, columns=None, item_cls=None, parent=None):
        super().__init__(parent=parent)
        self.archive = archive
        self.columns = columns or ['Name', 'Type']
        self._item_cls = item_cls or PathArchiveTreeItem
        self.root_item = None
        self._parent_cache = {'.': self.root_item}
        self._setup_root()

    def _setup_root(self):
        self.root_item = self._item_cls('root', model=self)

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
        parent_path, name = path.rsplit('/', maxsplit=1) if '/' in path else ('', path)
        if '.' in name:
            return self.parentForPath(parent_path)
        lower_path = path.lower()
        if lower_path not in self._parent_cache:
            parent = self.parentForPath(parent_path)
            self._parent_cache[lower_path] = self._item_cls(path, model=self, parent=parent)
        return self._parent_cache[lower_path]

    def itemForPath(self, path):
        if isinstance(path, Path):
            path = path.as_posix()
        if '/' in path:
            parent_path, name = path.rsplit('/', maxsplit=1) if '/' in path else ('', path)
            if parent := self._parent_cache.get(parent_path.lower()):
                return parent.children_by_name.get(name)
        return None

    def appendChildrenToPath(self, path, rows):
        if parent := self.parentForPath(path):
            parent.appendChildren(rows)


class PathArchiveTreeModelLoader(qtc.QRunnable):
    def __init__(self, scdv, model, item_cls, task_name='', task_status_msg='', load_limit=-1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv
        self.model = model
        self.signals = BackgroundRunnerSignals()
        self._item_cls = item_cls or PathArchiveTreeItem
        self._should_cancel = False
        self._load_limit = load_limit  # This is for dev/debugging purposes
        self.task_name = task_name or self.__class__.__name__
        self.task_status_message = task_status_msg
        self.signals.cancel.connect(self._handle_cancel)
        self.setAutoDelete(True)

    def _handle_cancel(self):
        self._should_cancel = True

    def items_to_load(self):
        return []

    def load_item(self, item):
        self._item_cls(item, model=self.model, parent=self.model.parentForPath(item))

    def run(self):
        items = self.items_to_load()

        if self.task_status_message:
            self.scdv.task_started.emit(self.task_name, self.task_status_message, 0, len(items))

        start_time = time.time()
        t = time.time()
        for i, f in enumerate(items):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                if self.task_status_message:
                    self.scdv.update_status_progress.emit(self.task_name, i, 0, 0, '')
                t = time.time()

            if 0 <= self._load_limit < i:
                break

            self.load_item(f)

        logger.debug(f'Loaded {self.task_name} in {timedelta(seconds=time.time()-start_time)}')
        if self.task_status_message:
            self.scdv.task_finished.emit(self.task_name, True, '')
        self.signals.finished.emit({})


class ContentItem:
    def __init__(self, name, path, contents=None):
        if contents is not None:
            if isinstance(contents, io.BytesIO):
                self._contents = contents
            elif isinstance(contents, str):
                self._contents = io.BytesIO(contents.encode('utf-8'))
            else:
                self._contents = io.BytesIO(contents)
        else:
            self._contents = io.BytesIO()
        self.name = name
        self.path = path

    def contents(self):
        return self._contents
