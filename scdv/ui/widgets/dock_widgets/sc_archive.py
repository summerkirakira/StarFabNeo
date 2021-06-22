import io
import os
import time
import shutil
from functools import cached_property, partial
from pathlib import Path

from qtpy.QtCore import Signal, Slot

from scdv.ui import qtc, qtw, qtg
from scdatatools.cry.cryxml import pprint_xml_tree, etree_from_cryxml_file
from scdv.ui.widgets.dcbrecord import DCBRecordItemView
from scdv.ui.widgets.dock_widgets.common import icon_provider, SCDVSearchableTreeDockWidget
from scdv.utils import show_file_in_filemanager
from scdv.ui.utils import ScrollMessageBox, ContentItem

SCFILEVIEW_COLUMNS = ['Name', 'Size', 'Kind', 'Date Modified', 'SearchColumn']
DCBVIEW_COLUMNS = ['Name', 'Type', 'GUID', 'SearchColumn']
RECORDS_ROOT_PATH = Path('libs/foundry/records')


class LoaderSignals(qtc.QObject):
    cancel = Signal()
    finished = Signal()


class P4KFileLoader(qtc.QRunnable):
    def __init__(self, scdv, model, archive, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv
        self.model = model
        self.archive = archive
        self.signals = LoaderSignals()
        self._node_cls = SCFileViewNode
        self._should_cancel = False
        self.signals.cancel.connect(self._handle_cancel)

    def _handle_cancel(self):
        self._should_cancel = True

    def run(self):
        self.scdv.task_started.emit('load_p4k', 'Opening Data.p4k', 0, 1)

        p4k = self.scdv.sc.p4k

        self.scdv.update_status_progress.emit('load_p4k', 1, 0, len(p4k.filelist), 'Loading Data.p4k')

        tmp = {}
        t = time.time()

        filelist = p4k.filelist.copy()
        self.scdv.p4k_opened.emit()
        try:
            p4k_limit = int(os.environ.get('SCDV_P4K_LIMIT', -1))
        except ValueError:
            p4k_limit = -1

        for i, f in enumerate(filelist):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_p4k', i, 0, 0, '')
                t = time.time()

            # This is for dev/debugging purposes
            if p4k_limit >= 0 and i > p4k_limit:
                break

            path = Path(f.filename)
            item = self._node_cls(path, info=f, parent_archive=p4k)
            tmp.setdefault(path.parent.as_posix(), []).append(item)

        for parent_path, rows in tmp.items():
            if self._should_cancel:
                return  # immediately break
            self.model.appendRowsToPath(parent_path, rows)

        self.scdv.task_finished.emit('load_p4k', True, '')
        self.signals.finished.emit()


class DCBLoader(P4KFileLoader):
    def __init__(self, scdv, model, *args, **kwargs):
        super().__init__(scdv, model, 'datacore', *args, **kwargs)
        self._node_cls = DCBViewNode

    @Slot()
    def run(self):
        self.scdv.task_started.emit('load_dcb', 'Opening Datacore', 0, 1)
        # TODO: Handle failing to open the datacore
        datacore = self.scdv.sc.datacore

        tmp = {}
        t = time.time()
        max = len(datacore.records)

        self.scdv.update_status_progress.emit('load_dcb', 1, 0, max, 'Loading Datacore')
        for i, r in enumerate(datacore.records):
            if self._should_cancel:
                return  # immediately break

            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_dcb', i, 0, max, 'Loading Datacore')
                t = time.time()

            path = Path(r.filename)
            item = self._node_cls(path, info=r, parent_archive=datacore)
            tmp.setdefault(path.relative_to(RECORDS_ROOT_PATH).parent.as_posix(), []).append(item)

        for parent_path, rows in tmp.items():
            if self._should_cancel:
                return  # immediately break
            self.model.appendRowsToPath(parent_path, rows)

        self.scdv.task_finished.emit('load_dcb', True, '')
        self.signals.finished.emit()


class SCFileViewNode(qtg.QStandardItem, ContentItem):
    def __init__(self, path: Path, info=None, parent_archive=None, *args, **kwargs):
        super().__init__(path.name, *args, **kwargs)
        ContentItem.__init__(self, path.name, path)

        self.setColumnCount(len(SCFILEVIEW_COLUMNS))
        self.setEditable(False)
        self.parent_archive = parent_archive
        self.info = info

        if self.path:
            if self.path.suffix:
                self.setIcon(icon_provider.icon(qtc.QFileInfo(str(self.path))))
            else:
                self.setIcon(icon_provider.icon(icon_provider.Folder))

    def _read_cryxml(self, f):
        try:
            c = pprint_xml_tree(etree_from_cryxml_file(f))
        except Exception as e:
            c = f'Failed to convert CryXmlB {self.name}: {e}'
        return c

    def contents(self):
        try:
            with self.parent_archive.open(self.path.as_posix()) as f:
                if f.read(7) == b'CryXmlB':
                    f.seek(0)
                    c = self._read_cryxml(f).encode('utf-8')
                else:
                    f.seek(0)
                    c = f.read()
        except Exception as e:
            c = f'Failed to read {self.name}: {e}'.encode('utf-8')
        return io.BytesIO(c)

    @cached_property
    def raw_size(self):
        if self.info is not None:
            return self.info.file_size
        elif self.hasChildren():
            return sum(
                self.child(r, 0).raw_size for r in range(self.rowCount())
            )
        return 0

    @cached_property
    def raw_time(self):
        if self.info is not None:
            return self.info.date_time
        elif self.hasChildren():
            return max(
                self.child(r, 0).raw_time for r in range(self.rowCount())
            )

    def clear_cache(self):
        for c in ['raw_size', 'raw_time', 'size', 'type', 'date_modified']:
            if c in self.__dict__:
                del self.__dict__[c]

    @cached_property
    def size(self):
        if self.info is not None:
            return qtc.QLocale().formattedDataSize(self.info.file_size)
        if self.hasChildren():
            return qtc.QLocale().formattedDataSize(self.raw_size)
        return ''

    @cached_property
    def type(self):
        return ''

    @cached_property
    def type(self):
        return self.path.suffix

    @cached_property
    def date_modified(self):
        if self.info is not None:
            return qtc.QDateTime(*self.info.date_time)  # .toString(qtc.Qt.DateFormat.SystemLocaleDate)
        if self.hasChildren():
            return qtc.QDateTime(*self.raw_time)  # .toString(qtc.Qt.DateFormat.SystemLocaleDate)
        return ''

    def extract_to(self, extract_path):
        self.parent_archive.extract(str(self.path.as_posix()), extract_path, convert_cryxml=True)

    def save_to(self, extract_path):
        self.parent_archive.save_to(str(self.path.as_posix()), extract_path, convert_cryxml=True)

    def __repr__(self):
        return f'<SCFileViewNode "{self.path.as_posix()}" archive:{self.parent_archive}>'


class SCFileViewModel(qtg.QStandardItemModel):
    def __init__(self, sc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColumnCount(len(SCFILEVIEW_COLUMNS))
        self.setHorizontalHeaderLabels(SCFILEVIEW_COLUMNS)
        self.sc = sc
        self._node_cls = SCFileViewNode
        self._cache = {}

    @property
    def paths(self):
        return list(self._cache.keys())

    def flags(self, index):
        return super().flags(index) & ~qtc.Qt.ItemIsEditable

    def data(self, index, role):
        if index.column() >= 1:
            i = self.itemFromIndex(self.createIndex(index.row(), 0, index.internalId()))
            if i is not None:
                if role == qtc.Qt.DisplayRole:
                    if index.column() == 1:
                        return i.size
                    elif index.column() == 2:
                        return i.type
                    elif index.column() == 3:
                        return i.date_modified
                    elif index.column() == 4:
                        return i.path.as_posix()
                elif role == qtc.Qt.UserRole:
                    if index.column() == 1:
                        return i.raw_size
                    elif index.column() == 3:
                        return i.raw_time
        return super().data(index, role)

    def itemForPath(self, path):
        return self._cache.get(path.as_posix() if isinstance(path, Path) else path)

    def appendRowsToPath(self, path, rows):
        if isinstance(path, str):
            path = Path(path)

        def get_or_create_parent(path):
            if str(path) == '.':
                return self.invisibleRootItem()
            elif path.as_posix() not in self._cache:
                p = get_or_create_parent(path.parent)
                p.appendRow(self._node_cls(path))
                self._cache[path.as_posix()] = p.child(p.rowCount() - 1)
            return self._cache.get(path.as_posix())

        parent = get_or_create_parent(path)
        if parent is not None:
            parent.appendRows(rows)
            if hasattr(parent, 'clear_cache'):
                parent.clear_cache()
            for row in rows:
                self._cache[row.path.as_posix()] = row


class DCBViewNode(qtg.QStandardItem, ContentItem):
    def __init__(self, path, info=None, parent_archive=None, *args, **kwargs):
        name = info.name if info is not None else path.name

        super().__init__(name, *args, **kwargs)
        ContentItem.__init__(self, name, path)

        self.guid = info.id.value if info is not None else ''
        self.type = info.type if info is not None else ''
        self.record = info
        self.contents_mode = 'json'

        self.parent_archive = parent_archive

        self.setColumnCount(len(DCBVIEW_COLUMNS))
        self.setEditable(False)

    def contents(self):
        if self.guid is not None:
            if self.contents_mode == 'xml':
                return io.BytesIO(
                    self.parent_archive.dump_record_xml(self.parent_archive.records_by_guid[self.guid]).encode('utf-8')
                )
            return io.BytesIO(
                self.parent_archive.dump_record_json(self.parent_archive.records_by_guid[self.guid]).encode('utf-8')
            )
        return io.BytesIO(b'')

    def __repr__(self):
        return f'<DCBViewNode {self.name} "{self.path.as_posix()}">'


class DCBFileViewModel(SCFileViewModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColumnCount(len(DCBVIEW_COLUMNS))
        self.setHorizontalHeaderLabels(DCBVIEW_COLUMNS)
        self.parent_archive = self.sc.datacore
        self._node_cls = DCBViewNode
        self._guid_cache = {}

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)

    def appendRowsToPath(self, path, rows):
        super().appendRowsToPath(path, rows)
        for row in rows:
            if row.guid:
                self._guid_cache[row.guid] = row

    def data(self, index, role):
        if index.column() >= 1 and role == qtc.Qt.DisplayRole:
            i = self.itemFromIndex(self.createIndex(index.row(), 0, index.internalId()))
            if i is not None:
                if index.column() == 1:
                    return i.type
                elif index.column() == 2:
                    return i.guid
                elif index.column() == 3:
                    return f'{i.guid}:{i.path.as_posix()}'
        return qtg.QStandardItemModel.data(self, index, role)


class P4KSortFilterProxyModel(qtc.QSortFilterProxyModel):
    def lessThan(self, source_left, source_right):
        if self.sortColumn() in [1, 3]:
            return (self.sourceModel().data(source_left, qtc.Qt.UserRole) <
                    self.sourceModel().data(source_right, qtc.Qt.UserRole))
        else:
            return super().lessThan(source_left, source_right)


class P4KViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Data.p4k'))
        self.scdv.opened.connect(self.handle_sc_opened)

        self.sc_tree_model = None

        self.ctx_manager.default_menu.addSeparator()
        save_file = self.ctx_manager.default_menu.addAction('Save To...')
        save_file.triggered.connect(partial(self.ctx_manager.handle_action, 'save_to'))
        extract = self.ctx_manager.default_menu.addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        extract = self.ctx_manager.menus[''].addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))

        # self.proxy_model = qtc.QSortFilterProxyModel(parent=self)
        self.proxy_model = P4KSortFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(False)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(4)

    @Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = super()._on_ctx_triggered(action)

        # Item Actions
        if not selected_items:
            return

        if action == 'extract':
            # TODO: add extraction dialog with options, like auto_convert_cryxmlb and auto unsplit dds
            edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Extract to...')
            if edir:
                total = len(selected_items)
                self.scdv.task_started.emit('extract', f'Extraction to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    self.scdv.update_status_progress.emit('extract', 1, 0, total,
                                                          f'Extracting {item.path.name} to {edir}')
                    try:
                        item.extract_to(edir)
                    except Exception as e:
                        print(e)

                self.scdv.task_finished.emit('extract', True, '')
                show_file_in_filemanager(Path(edir))
        elif action == 'save_to':
            edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Save To...')
            if edir:
                total = len(selected_items)
                self.scdv.task_started.emit('extract', f'Saving to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    self.scdv.update_status_progress.emit('extract', 1, 0, total,
                                                          f'Extracting {item.path.name} to {edir}')
                    try:
                        item.save_to(edir)
                    except Exception as e:
                        print(e)

                self.scdv.task_finished.emit('extract', True, '')
                show_file_in_filemanager(Path(edir))

    def _finished_loading(self):
        self.proxy_model.paths = list(self.scdv.sc.p4k.NameToInfo.keys())
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.sc_tree.hideColumn(4)
        self.raise_()
        self.scdv.p4k_loaded.emit()

    def handle_sc_opened(self):
        if self.scdv.sc is not None:
            self.show()
            self.sc_tree_model = SCFileViewModel(self.scdv.sc, parent=self)
            loader = P4KFileLoader(self.scdv, self.sc_tree_model, 'p4k')
            self.closing.connect(lambda: loader.signals.cancel.emit())
            loader.signals.finished.connect(self._finished_loading)
            self.sc_tree_thread_pool.start(loader)

    def _on_doubleclick(self, index):
        index = self.proxy_model.mapToSource(index)
        item = self.sc_tree_model.itemFromIndex(index)
        try:
            if item is not None:
                if '.dds' in item.path.name:
                    parent = self.sc_tree_model.itemForPath(item.path.parent)
                    basename = f'{item.path.name.split(".dds")[0]}.dds'
                    items = [parent.child(i) for i in range(parent.rowCount())]
                    items = sorted([_ for _ in items if _.path.name.startswith(basename)],
                                   key=lambda item: item.path.as_posix())

                    self._handle_item_action({items[0].path.as_posix(): items}, self.sc_tree_model, index)
                else:
                    self._handle_item_action(item, self.sc_tree_model, index)
        except Exception as e:
            ScrollMessageBox.critical(self, "Error opening file", f"{e}")


class DCBViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Datacore'))
        self.scdv.p4k_loaded.connect(self.handle_p4k_opened)
        self.sc_tree_thread_pool = qtc.QThreadPool()

        self.sc_tree_model = None
        self.proxy_model = qtc.QSortFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(False)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(3)

    @Slot()
    def _finished_loading(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.sc_tree.hideColumn(3)
        self.raise_()
        self.scdv.datacore_loaded.emit()

    def handle_p4k_opened(self):
        if self.scdv.sc is not None:
            self.show()
            self.sc_tree_model = DCBFileViewModel(self.scdv.sc, parent=self)
            loader = DCBLoader(self.scdv, self.sc_tree_model)
            self.closing.connect(lambda: loader.signals.cancel.emit())
            loader.signals.finished.connect(self._finished_loading)
            self.sc_tree_thread_pool.start(loader)

    def _handle_item_action(self, item, model, index):
        if isinstance(item, DCBViewNode) and item.record is not None:
            widget = DCBRecordItemView(item, self.scdv)
            self.scdv.add_tab_widget(item.path, widget, item.name, tooltip=item.path.as_posix())
            # TODO: error dialog
