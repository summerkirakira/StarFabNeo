import io
import os
from functools import cached_property

from scdatatools.engine.cryxml import pprint_xml_tree, etree_from_cryxml_file, is_cryxmlb_file

from starfab.log import getLogger
from starfab.gui import qtc, qtw, qtg
from starfab.models.common import PathArchiveTreeSortFilterProxyModel, PathArchiveTreeItem, ContentItem, \
    PathArchiveTreeModelLoader, ThreadLoadedPathArchiveTreeModel


logger = getLogger(__name__)
P4K_MODEL_COLUMNS = ['Name', 'Size', 'Kind', 'Date Modified']


class P4KSortFilterProxyModelArchive(PathArchiveTreeSortFilterProxyModel):
    def lessThan(self, source_left, source_right):
        if self.sortColumn() in [1, 3]:
            return (self.sourceModel().data(source_left, qtc.Qt.UserRole) <
                    self.sourceModel().data(source_right, qtc.Qt.UserRole))
        return super().lessThan(source_left, source_right)


class P4KItem(PathArchiveTreeItem, ContentItem):
    _cached_properties_ = PathArchiveTreeItem._cached_properties_ + ['raw_size', 'raw_time', 'size', 'date_modified']

    def _read_cryxml(self, f):
        try:
            c = pprint_xml_tree(etree_from_cryxml_file(f))
        except Exception as e:
            c = f'Failed to convert CryXmlB {self.name}: {e}'
        return c

    def contents(self):
        try:
            with self.model.archive.open(self._path) as f:
                if is_cryxmlb_file(f):
                    return io.BytesIO(self._read_cryxml(f).encode('utf-8'))
                return io.BytesIO(f.read())
        except Exception as e:
            return io.BytesIO(f'Failed to read {self.name}: {e}'.encode('utf-8'))

    @cached_property
    def info(self):
        return self.model.archive.NameToInfo.get(self._path)

    @cached_property
    def raw_size(self):
        if self.info is not None:
            return self.info.file_size
        elif self.children:
            child_sizes = [_.raw_size for _ in self.children if _.raw_size is not None]
            if child_sizes:
                return sum(child_sizes)
        return None

    @cached_property
    def raw_time(self):
        if self.info is not None:
            return self.info.date_time
        elif self.children:
            child_times = [_.raw_time for _ in self.children if _.raw_time is not None]
            if child_times:
                return max(child_times)
        return None

    @cached_property
    def size(self):
        if os.environ.get('STARFAB_QUICK'):
            return ''
        if self.raw_size is not None:
            return qtc.QLocale().formattedDataSize(self.raw_size)
        return ''

    @cached_property
    def date_modified(self):
        if os.environ.get('STARFAB_QUICK'):
            return ''
        if self.raw_time is not None:
            return qtc.QDateTime(*self.raw_time)  # .toString(qtc.Qt.DateFormat.SystemLocaleDate)
        return ''

    def extract_to(self, extract_path):
        self.model.archive.extract(str(self.path.as_posix()), extract_path)

    def save_to(self, extract_path):
        self.model.archive.save_to(str(self.path.as_posix()), extract_path, convert_cryxml=True)

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.name
            elif column == 1:
                return self.size
            elif column == 2:
                return self.suffix
            elif column == 3:
                return self.date_modified
            else:
                return ''
        if role == qtc.Qt.UserRole:
            if column == 1:
                return self.raw_size
            if column == 2:
                return self.suffix
            if column == 3:
                return self.raw_time

        return super().data(column, role)

    def __repr__(self):
        return f'<P4KTreeItem "{self._path}" archive:{self.model.archive}>'


class P4KModelLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        return self.model.archive.filelist

    def load_item(self, item):
        self._item_cls(item.filename, model=self.model, parent=self.model.parentForPath(item.filename))


class P4KModel(ThreadLoadedPathArchiveTreeModel):
    def __init__(self, sc_manager):
        self._sc_manager = sc_manager
        super().__init__(None, columns=P4K_MODEL_COLUMNS, item_cls=P4KItem, parent=sc_manager,
                         loader_cls=P4KModelLoader, loader_task_name='load_p4k_model',
                         loader_task_status_msg='Processing Data.p4k')
