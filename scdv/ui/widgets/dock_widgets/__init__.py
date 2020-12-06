import io
import time
from pathlib import Path
from functools import partial, cached_property

from qtpy import uic
from qtpy.QtCore import Slot, Signal

from scdatatools.cryxml import pprint_xml_tree, etree_from_cryxml_file

from scdv.ui import qtc, qtg, qtw
from scdv.resources import RES_PATH
from scdv.utils import show_file_in_filemanager
from scdv.ui.widgets.editor import Editor, SUPPORTED_EDITOR_FORMATS
from scdv.ui.widgets.dcbrecord import DCBRecordItemView
from scdv.ui.widgets.image_viewer import QImageViewer, SUPPORTED_IMG_FORMATS
from .pyconsole import PyConsoleDockWidget

SCFILEVIEW_COLUMNS = ['Name', 'Size', 'Kind', 'Date Modified', 'SearchColumn']
DCBVIEW_COLUMNS = ['Name', 'Type', 'GUID', 'SearchColumn']

icon_provider = qtw.QFileIconProvider()


class SCDVContextMenuManager(qtc.QObject):
    action_triggered = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_menu = qtw.QMenu()
        expand_all = self.default_menu.addAction('Expand All')
        expand_all.triggered.connect(partial(self.handle_action, 'expand_all'))
        collapse_all = self.default_menu.addAction('Collapse All')
        collapse_all.triggered.connect(partial(self.handle_action, 'collapse_all'))
        self._menus = {}


    @Slot(str)
    def handle_action(self, action):
        self.action_triggered.emit(action)

    def menu_for_path(self, path):
        if isinstance(path, str):
            path = Path(path)
        return self._menus.get(path.suffix, self.default_menu)


class SCDVDockWidget(qtw.QDockWidget):
    def __init__(self, scdv, *args, **kwargs):
        super().__init__(parent=scdv, *args, **kwargs)
        self.scdv = scdv
        self.ctx_manager = SCDVContextMenuManager()
        self.ctx_manager.action_triggered.connect(self._on_ctx_triggered)
        self._ctx_item = None

    @Slot(str)
    def _on_ctx_triggered(self, action):
        pass

    def _handle_item_action(self, item):
        if item is None:
            return

        widget = None

        if item.path.suffix.lower()[1:] in SUPPORTED_EDITOR_FORMATS:
            widget = Editor(item)
        elif item.path.suffix.lower() in SUPPORTED_IMG_FORMATS:
            widget = QImageViewer.fromFile(item.contents())

        if widget is not None:
            self.scdv.add_tab_widget(item.path, widget, item.path.name)


class SCDVSearchableTreeDockWidget(SCDVDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(str(RES_PATH / 'ui' / 'FileViewDock.ui'), self)

        self.sc_tree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tree.customContextMenuRequested.connect(self._show_ctx_menu)
        self.sc_tree.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.sc_tree.setSortingEnabled(True)

        self.sc_tree_search.returnPressed.connect(self.on_search_changed)
        self.sc_search.clicked.connect(self.on_search_changed)
        self.sc_tree.doubleClicked.connect(self._on_doubleclick)

        shortcut = qtw.QShortcut(self.sc_tree)
        shortcut.setKey(qtg.QKeySequence("Return"))
        shortcut.setContext(qtc.Qt.WidgetShortcut)
        shortcut.activated.connect(self._on_enter_pressed)

    def _on_enter_pressed(self):
        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        for index in selection:
            self._on_doubleclick(index)

    def _on_doubleclick(self, index):
        item = self.sc_tree_model.itemFromIndex(self.proxy_model.mapToSource(index))
        if item is not None:
            self._handle_item_action(item)

    @Slot(qtc.QPoint)
    def _show_ctx_menu(self, pos):
        self._ctx_item = self.sc_tree.indexAt(pos)
        menu = self.ctx_manager.menu_for_path("")
        menu.exec_(self.sc_tree.mapToGlobal(pos))

    @Slot(str)
    def _on_ctx_triggered(self, action):
        if action == 'collapse_all':
            self.sc_tree.collapseAll()
            return []

        selected_items = []

        def _add_indexes(indexes):
            for i in indexes:
                if self.proxy_model.hasChildren(i):
                    children = [self.proxy_model.index(_, 0, i)
                                for _ in range(0, self.proxy_model.rowCount(i))]
                    _add_indexes(children)
                else:
                    selected_items.append(self.sc_tree_model.itemFromIndex(self.proxy_model.mapToSource(i)))

        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        if not selection and self._ctx_item is not None:
            selection = [self._ctx_item]

        # Index Actions
        if action == 'expand_all':
            for index in selection:
                self.sc_tree.expandRecursively(index)
            return []

        _add_indexes(selection)
        return selected_items

    @Slot(str)
    def on_search_changed(self):
        text = self.sc_tree_search.text()
        self.proxy_model.setFilterRegExp(text)


class LoaderSignals(qtc.QObject):
    finished = Signal()


class P4KFileLoader(qtc.QRunnable):
    def __init__(self, scdv, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv
        self.model = model
        self.signals = LoaderSignals()

    @Slot()
    def run(self):
        self.scdv.task_started.emit('load_p4k', 'Opening Data.p4k', 0, 1)

        p4k = self.scdv.sc.p4k

        self.scdv.update_status_progress.emit('load_p4k', 1, 0, len(p4k.filelist), 'Loading Data.p4k')

        tmp = {}
        t = time.time()

        filelist = p4k.filelist.copy()
        self.scdv.p4k_opened.emit()

        for i, f in enumerate(filelist):
            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_p4k', i, 0, 0, '')
                t = time.time()
            # if i > 10000:
            #     break
            parent, item = self.model.create_item(Path(f.filename), info=f, parent_archive=p4k)
            tmp.setdefault(parent.path, []).append(item)

        for parent_path, rows in tmp.items():
            self.model.appendRowsToPath(parent_path, rows)

        self.scdv.task_finished.emit('load_p4k', True, '')
        self.signals.finished.emit()


class SCFileViewNode(qtg.QStandardItem):
    def __init__(self, path: Path, info=None, parent_archive=None, *args, **kwargs):
        self.path = path
        self.name = path.name

        super().__init__(self.name, *args, **kwargs)

        self.setColumnCount(len(SCFILEVIEW_COLUMNS))
        self.setEditable(False)
        self.parent_archive = parent_archive
        self.info = info

        if self.path:
            if self.path.suffix:
                self.setIcon(icon_provider.icon(qtc.QFileInfo(str(self.path))))
            else:
                self.setIcon(icon_provider.icon(icon_provider.Folder))

    def _read_cryxml(self):
        try:
            with self.parent_archive.open(self.path.as_posix()) as f:
                c = pprint_xml_tree(etree_from_cryxml_file(f))
        except Exception as e:
            c = f'Failed to convert CryXmlB {self.name}: {e}'
        return c

    def contents(self):
        try:
            if self.path.suffix == '.xml':
                with self.parent_archive.open(self.path.as_posix()) as f:
                    if f.read(7) == b'CryXmlB':
                        c = self._read_cryxml().encode('utf-8')
            else:
                with self.parent_archive.open(self.path.as_posix(), 'r') as f:
                    c = f.read()
        except Exception as e:
            c = f'Failed to read {self.name}: {e}'.encode('utf-8')
        return io.BytesIO(c)

    @cached_property
    def size(self):
        if self.info is not None:
            return qtc.QLocale().formattedDataSize(self.info.file_size)
        return ''

    @cached_property
    def type(self):
        return self.path.suffix

    @cached_property
    def date_modified(self):
        if self.info is not None:
            return qtc.QDateTime(*self.info.date_time).toString(qtc.Qt.DateFormat.SystemLocaleDate)
        return ''

    def extract_to(self, extract_path):
        self.parent_archive.extract(self.path.as_posix(), extract_path)

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

    def create_item(self, path, info=None, parent_archive=None):
        str_parent = path.parent.as_posix()
        if str_parent == '.':
            parent = self.invisibleRootItem()
        elif str_parent not in self._cache:
            p, r = self.create_item(path.parent)
            p.appendRow(r)
            parent = p.child(p.rowCount() - 1)
            self._cache[str_parent] = parent
        else:
            parent = self._cache[str_parent]

        item = self._node_cls(path, info=info, parent_archive=parent_archive)
        self._cache[path.as_posix()] = item
        return parent, item

    def flags(self, index):
        return super().flags(index) & ~qtc.Qt.ItemIsEditable

    def data(self, index, role):
        if index.column() >= 1 and role == qtc.Qt.DisplayRole:
            i = self.itemFromIndex(self.createIndex(index.row(), 0, index.internalId()))
            if i is not None:
                if index.column() == 1:
                    return i.size
                elif index.column() == 2:
                    return i.type
                elif index.column() == 3:
                    return i.date_modified
                elif index.column() == 4:
                    return i.path.as_posix()
        return super().data(index, role)

    def itemForPath(self, path):
        return self._cache.get(path.as_posix() if isinstance(path, Path) else path)

    def appendRowsToPath(self, path, rows):
        if path.as_posix() not in self._cache:
            return
        self._cache[path.as_posix()].appendRows(rows)


class DCBLoader(qtc.QRunnable):
    def __init__(self, scdv, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scdv = scdv
        self.model = model
        self.signals = LoaderSignals()

    @Slot()
    def run(self):
        self.scdv.task_started.emit('load_dcb', 'Opening Datacore', 0, 1)
        datacore = self.scdv.sc.datacore

        tmp = {}
        t = time.time()
        max = len(datacore.records)

        self.scdv.update_status_progress.emit('load_dcb', 1, 0, max, 'Loading Datacore')
        for i, r in enumerate(datacore.records):
            if (time.time() - t) > 0.5:
                self.scdv.update_status_progress.emit('load_dcb', i, 0, max, 'Loading Datacore')
                t = time.time()

            parent, item = self.model.create_item(Path(r.filename), info=r, parent_archive=datacore)
            tmp.setdefault(parent.path, []).append(item)

        for parent_path, rows in tmp.items():
            self.model.appendRowsToPath(parent_path, rows)

        self.scdv.task_finished.emit('load_dcb', True, '')
        self.signals.finished.emit()


class DCBViewNode(qtg.QStandardItem):
    def __init__(self, path, info=None, parent_archive=None, *args, **kwargs):
        self.path = path

        self.name = info.name if info is not None else self.path.name
        self.guid = info.id.value if info is not None else ''
        self.type = info.type if info is not None else ''
        self.record = info

        self.parent_archive = parent_archive
        super().__init__(self.name, *args, **kwargs)

        self.setColumnCount(len(DCBVIEW_COLUMNS))
        self.setEditable(False)

    def contents(self):
        if self.guid is not None:
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
        self._node_cls = DCBViewNode
        self.parent_archive = self.sc.datacore
        self._guid_cache = {}

    def create_item(self, path, info=None, parent_archive=None):
        parent, item = super().create_item(path, info, parent_archive)
        if item.guid:
            self._guid_cache[item.guid] = item
        return parent, item

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)

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


class P4KViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Data.p4k'))
        self.scdv.opened.connect(self.handle_sc_opened)
        self.sc_tree_thread_pool = qtc.QThreadPool()

        self.sc_tree_model = None

        self.ctx_manager.default_menu.addSeparator()
        extract = self.ctx_manager.default_menu.addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))

        self.proxy_model = qtc.QSortFilterProxyModel(parent=self)
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

    @Slot()
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
            loader = P4KFileLoader(self.scdv, self.sc_tree_model)
            loader.signals.finished.connect(self._finished_loading)
            self.sc_tree_thread_pool.start(loader)


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

    def handle_p4k_opened(self):
        if self.scdv.sc is not None:
            self.show()
            self.sc_tree_model = DCBFileViewModel(self.scdv.sc, parent=self)
            loader = DCBLoader(self.scdv, self.sc_tree_model)
            loader.signals.finished.connect(self._finished_loading)
            self.sc_tree_thread_pool.start(loader)

    def _handle_item_action(self, item):
        if item is None:
            return

        if isinstance(item, DCBViewNode) and item.record is not None:
            widget = DCBRecordItemView(item, self.scdv)
            self.scdv.add_tab_widget(item.path, widget, item.name, tooltip=item.path.as_posix())
            # TODO: error dialog


class SCFileSystemProxyModel(qtc.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.archive_sources = []

    def filterAcceptsRow(self, source_row, source_parent):
        if source_parent == self.sourceModel().index(self.sourceModel().rootPath()):
            return super().filterAcceptsRow(source_row, source_parent)
        return True


class FileSystemWrapper:
    def __init__(self, path):
        self.path = path
        self.name = path.name

    def contents(self):
        try:
            with self.path.open('rb') as f:
                c = f.read()
        except Exception as e:
            c = f'Failed to read {self.name}: {e}'.encode('utf-8')
        return io.BytesIO(c)


class FileViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr('Local Files'))
        self.scdv.opened.connect(self.handle_file_opened)

        self.sc_tree_model = qtw.QFileSystemModel()
        self.proxy_model = SCFileSystemProxyModel(self)
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(0)
        self.sc_tree.setModel(self.proxy_model)

    def _on_doubleclick(self, index):
        item = FileSystemWrapper(Path(self.sc_tree_model.filePath(self.proxy_model.mapToSource(index))))
        if item is not None:
            self._handle_item_action(item)

    def handle_file_opened(self):
        if self.scdv.sc is not None:
            self.sc_tree_model.setRootPath(str(self.scdv.sc.game_folder))
            self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
            self.sc_tree.setRootIndex(
                self.proxy_model.mapFromSource(self.sc_tree_model.index(str(self.scdv.sc.game_folder)))
            )
            header = self.sc_tree.header()
            header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
