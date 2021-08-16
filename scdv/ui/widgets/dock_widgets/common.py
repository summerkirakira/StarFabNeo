import logging
import typing
import operator
from functools import partial
from pathlib import Path

from qtpy import uic
from scdv.ui import qtc

from scdv.ui import qtc, qtw, qtg
from scdv.resources import RES_PATH
from scdv.ui.common import PathArchiveTreeSortFilterProxyModel
from scdv.ui.widgets.editor import SUPPORTED_EDITOR_FORMATS, Editor
from scdv.ui.widgets.image_viewer import SUPPORTED_IMG_FORMATS, QImageViewer, DDSImageViewer
from scdv.ui.widgets.chunked_file_viewer import SUPPORTED_CHUNK_FILE_FORMATS, ChunkedObjView

logger = logging.getLogger(__name__)


class SCDVContextMenuManager(qtc.QObject):
    action_triggered = qtc.Signal(str)

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

    @qtc.Slot(str)
    def handle_action(self, action):
        self.action_triggered.emit(action)

    def menu_for_path(self, path):
        if isinstance(path, str):
            path = Path(path)
        return self.menus.get(path.suffix, self.default_menu)


class SCDVDockWidget(qtw.QDockWidget):
    __ui_file__ = None

    closing = qtc.Signal()

    def __init__(self, scdv, *args, **kwargs):
        super().__init__(parent=scdv, *args, **kwargs)
        if self.__ui_file__ is not None:
            uic.loadUi(self.__ui_file__, self)
        self.scdv = scdv
        self.ctx_manager = SCDVContextMenuManager()
        self.ctx_manager.action_triggered.connect(self._on_ctx_triggered)
        self._ctx_item = None

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        pass

    def _handle_item_action(self, item, model, index):
        widget = None

        if isinstance(item, dict):
            # TODO: this needs be handled much better than "is it a dict" -.-'
            widget = DDSImageViewer(list(item.values())[0])
            item = widget.dds_header
        elif item.suffix.lower() in SUPPORTED_EDITOR_FORMATS:
            widget = Editor(item)
        elif item.suffix.lower() in SUPPORTED_CHUNK_FILE_FORMATS:
            widget = ChunkedObjView(item)
        elif item.suffix.lower() in SUPPORTED_IMG_FORMATS:
            widget = QImageViewer.fromFile(item.contents())

        if widget is not None:
            self.scdv.add_tab_widget(item.path, widget, item.path.name)


class SCDVSearchableTreeFilterWidget(qtw.QWidget):
    filter_changed = qtc.Signal()
    remove_filter = qtc.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def compile_filter(self) -> (typing.Callable, typing.Callable):
        return operator.and_, lambda i: True

    def close_filter(self):
        self.remove_filter.emit()


class SCDVSearchableTreeDockWidget(SCDVDockWidget):
    __ui_file__ = str(RES_PATH / 'ui' / 'FileViewDock.ui')

    def __init__(self, scdv, proxy_model=None, *args, **kwargs):
        super().__init__(scdv, *args, **kwargs)

        self.sc_breadcrumbs.setVisible(False)
        self.sc_breadcrumbs.linkActivated.connect(self._handle_breadcrumbs)

        self.sc_tree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tree.customContextMenuRequested.connect(self._show_ctx_menu)
        self.sc_tree.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.sc_tree.setSortingEnabled(True)

        self.sc_add_filter.clicked.connect(self._handle_add_filter)
        self.sc_add_filter.setIcon(qtw.QApplication.style().standardIcon(qtw.QStyle.SP_FileDialogDetailedView))
        self.sc_add_filter.hide()

        self.sc_tree_search.editingFinished.connect(self._handle_search_changed)
        self.sc_search.clicked.connect(self._handle_search_changed)
        self.sc_tree.doubleClicked.connect(self._on_doubleclick)

        shortcut = qtw.QShortcut(self.sc_tree)
        shortcut.setKey(qtg.QKeySequence("Return"))
        shortcut.setContext(qtc.Qt.WidgetShortcut)
        shortcut.activated.connect(self._on_enter_pressed)

        self.sc_tree_model = None
        if proxy_model is not None:
            self.proxy_model = proxy_model(parent=self)
        else:
            self.proxy_model = PathArchiveTreeSortFilterProxyModel(parent=self)
        self.sc_tree.setModel(self.proxy_model)

    def _filters_changed(self):
        fl = self.filter_widgets.layout()
        self.proxy_model.setAdditionFilters([
            cf for i in range(fl.count()) if (cf := fl.itemAt(i).widget().compile_filter()) is not None
        ])

    def _create_filter(self):
        raise NotImplementedError()

    def _handle_remove_filter(self):
        sender = self.sender()
        layout = self.filter_widgets.layout()
        if (index := layout.indexOf(sender)) >= 0:
            widget = layout.takeAt(index).widget()
            widget.setParent(None)
            del widget
        self._filters_changed()

    def _handle_add_filter(self):
        filter_widget = self._create_filter()
        filter_widget.filter_changed.connect(self._filters_changed)
        filter_widget.remove_filter.connect(self._handle_remove_filter)
        self.filter_widgets.layout().addWidget(filter_widget)

    def _handle_breadcrumbs(self, link):
        pass

    def _on_enter_pressed(self):
        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        for index in selection:
            self._on_doubleclick(index)

    def _on_doubleclick(self, index):
        index = self.proxy_model.mapToSource(index)
        item = index.internalPointer()
        if item is not None:
            self._handle_item_action(item, self.sc_tree_model, index)

    @qtc.Slot(qtc.QPoint)
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
                    selected_items.append(self.proxy_model.mapToSource(i).internalPointer())

        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        if not selection and self._ctx_item is not None:
            selection = [self._ctx_item]

        _add_indexes(selection)
        return selected_items

    @qtc.Slot(str)
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

    def _handle_item_action(self, item, model, index):
        pass

    @qtc.Slot(str)
    def _handle_search_changed(self):
        self.proxy_model.setFilterText(self.sc_tree_search.text())

    def deleteLater(self):
        self.closing.emit()
        super().deleteLater()


