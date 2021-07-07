from functools import partial
from pathlib import Path

from qtpy import uic
from qtpy.QtCore import Signal, Slot

from scdv.ui import qtc, qtw, qtg
from scdv.resources import RES_PATH
from scdv.ui.widgets.editor import SUPPORTED_EDITOR_FORMATS, Editor
from scdv.ui.widgets.image_viewer import SUPPORTED_IMG_FORMATS, QImageViewer, DDSImageViewer
from scdv.ui.widgets.chunked_file_viewer import SUPPORTED_CHUNK_FILE_FORMATS, ChunkedObjView

icon_provider = qtw.QFileIconProvider()


class SCDVContextMenuManager(qtc.QObject):
    action_triggered = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_menu = qtw.QMenu()
        open = self.default_menu.addAction('Open')
        open.triggered.connect(partial(self.handle_action, 'doubleclick'))

        self.menus = {'': qtw.QMenu()}
        expand_all = self.menus[''].addAction('Expand All')
        expand_all.triggered.connect(partial(self.handle_action, 'expand_all'))
        collapse_all = self.menus[''].addAction('Collapse All')
        collapse_all.triggered.connect(partial(self.handle_action, 'collapse_all'))

    @Slot(str)
    def handle_action(self, action):
        self.action_triggered.emit(action)

    def menu_for_path(self, path):
        if isinstance(path, str):
            path = Path(path)
        return self.menus.get(path.suffix, self.default_menu)


class SCDVDockWidget(qtw.QDockWidget):
    __ui_file__ = None

    closing = Signal()

    def __init__(self, scdv, *args, **kwargs):
        super().__init__(parent=scdv, *args, **kwargs)
        if self.__ui_file__ is not None:
            uic.loadUi(self.__ui_file__, self)
        self.scdv = scdv
        self.ctx_manager = SCDVContextMenuManager()
        self.ctx_manager.action_triggered.connect(self._on_ctx_triggered)
        self._ctx_item = None

    @Slot(str)
    def _on_ctx_triggered(self, action):
        pass

    def _handle_item_action(self, item, model, index):
        widget = None

        if isinstance(item, dict):
            widget = DDSImageViewer(list(item.values())[0])
            item = widget.dds_header
        elif item.path.suffix.lower()[1:] in SUPPORTED_EDITOR_FORMATS:
            widget = Editor(item)
        elif item.path.suffix.lower()[1:] in SUPPORTED_CHUNK_FILE_FORMATS:
            widget = ChunkedObjView(item)
        elif item.path.suffix.lower() in SUPPORTED_IMG_FORMATS:
            widget = QImageViewer.fromFile(item.contents())

        if widget is not None:
            self.scdv.add_tab_widget(item.path, widget, item.path.name)


class SCDVSearchableTreeDockWidget(SCDVDockWidget):
    __ui_file__ = str(RES_PATH / 'ui' / 'FileViewDock.ui')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.sc_breadcrumbs.setVisible(False)
        self.sc_breadcrumbs.linkActivated.connect(self._handle_breadcrumbs)

        self.sc_tree_thread_pool = qtc.QThreadPool(self)
        self.sc_tree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tree.customContextMenuRequested.connect(self._show_ctx_menu)
        self.sc_tree.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.sc_tree.setSortingEnabled(True)

        self.sc_tree_search.editingFinished.connect(self.on_search_changed)
        self.sc_search.clicked.connect(self.on_search_changed)
        self.sc_tree.doubleClicked.connect(self._on_doubleclick)

        shortcut = qtw.QShortcut(self.sc_tree)
        shortcut.setKey(qtg.QKeySequence("Return"))
        shortcut.setContext(qtc.Qt.WidgetShortcut)
        shortcut.activated.connect(self._on_enter_pressed)

        self.sc_tree_model = None
        self.proxy_model = qtc.QSortFilterProxyModel(parent=self)
        self.proxy_model.setDynamicSortFilter(False)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(0)
        self.sc_tree.setModel(self.proxy_model)

    def _handle_breadcrumbs(self, link):
        pass

    def _on_enter_pressed(self):
        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        for index in selection:
            self._on_doubleclick(index)

    def _on_doubleclick(self, index):
        item = self.sc_tree_model.itemFromIndex(self.proxy_model.mapToSource(index))
        if item is not None:
            self._handle_item_action(item, self.sc_tree_model, self.proxy_model.mapToSource(index))

    @Slot(qtc.QPoint)
    def _show_ctx_menu(self, pos):
        self._ctx_item = self.sc_tree.indexAt(pos)
        try:
            if isinstance(self.sc_tree_model, qtw.QFileSystemModel):
                path = self.sc_tree_model.filePath(self.proxy_model.mapToSource(self._ctx_item))
            else:
                path = self.sc_tree_model.itemFromIndex(self.proxy_model.mapToSource(self._ctx_item)).path
        except Exception as e:
            path = ""
        menu = self.ctx_manager.menu_for_path(path)
        menu.exec_(self.sc_tree.mapToGlobal(pos))

    def get_selected_items(self):
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

        _add_indexes(selection)
        return selected_items

    @Slot(str)
    def _on_ctx_triggered(self, action):
        if action == 'collapse_all':
            self.sc_tree.collapseAll()
            return []
        elif action == 'doubleclick':
            return self._on_doubleclick(self._ctx_item) if self._ctx_item is not None else None
        elif action == 'expand_all':
            selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
            if not selection and self._ctx_item is not None:
                selection = [self._ctx_item]
            for index in selection:
                self.sc_tree.expandRecursively(index)
            return []
        return self.get_selected_items()


    @Slot(str)
    def on_search_changed(self):
        text = self.sc_tree_search.text()
        self.proxy_model.setFilterRegExp(text)

    def deleteLater(self):
        self.closing.emit()
        self.sc_tree_thread_pool.waitForDone()
        super().deleteLater()
