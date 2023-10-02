import operator
import qtawesome as qta
import typing
from functools import partial
from pathlib import Path
from qtpy import uic

from starfab import get_starfab
from starfab.gui import qtc, qtw, qtg
from starfab.gui.widgets.chunked_file_viewer import (
    SUPPORTED_CHUNK_FILE_FORMATS,
    ChunkedObjView,
)
from starfab.gui.widgets.editor import SUPPORTED_EDITOR_FORMATS, Editor
from starfab.gui.widgets.image_viewer import (
    SUPPORTED_IMG_FORMATS,
    QImageViewer,
    DDSImageViewer,
)
from starfab.log import getLogger
from starfab.models.common import PathArchiveTreeSortFilterProxyModel
from starfab.resources import RES_PATH
from starfab.settings import settings
from starfab.utils import parsebool

logger = getLogger(__name__)


class StarFabContextMenuManager(qtc.QObject):
    action_triggered = qtc.Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_menu = qtw.QMenu()
        open = self.default_menu.addAction("Open")
        open.triggered.connect(partial(self.handle_action, "doubleclick"))

        self.menus = {"": qtw.QMenu()}
        expand_all = self.menus[""].addAction("Expand All")
        expand_all.triggered.connect(partial(self.handle_action, "expand_all"))
        collapse_all = self.menus[""].addAction("Collapse All")
        collapse_all.triggered.connect(partial(self.handle_action, "collapse_all"))

    @qtc.Slot(str)
    def handle_action(self, action):
        self.action_triggered.emit(action)

    def menu_for_path(self, path):
        if isinstance(path, str):
            path = Path(path)
        return self.menus.get(path.suffix, self.default_menu)


class StarFabDockWidget(qtw.QDockWidget):
    __ui_file__ = None

    closing = qtc.Signal()

    def __init__(self, starfab, *args, **kwargs):
        super().__init__(parent=starfab, *args, **kwargs)
        if self.__ui_file__ is not None:
            uic.loadUi(self.__ui_file__, self)
        self.starfab = starfab
        self.ctx_manager = StarFabContextMenuManager()
        self.ctx_manager.action_triggered.connect(self._on_ctx_triggered)
        self._ctx_item = None

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        pass

    def _handle_item_action(self, item, model, index):
        widget = None

        if isinstance(item, dict):
            # TODO: this needs be handled much better than "is it a dict" -.-'
            widget = DDSImageViewer(item)
            item = widget.dds_header
        elif item.path.suffix.lower() in SUPPORTED_EDITOR_FORMATS:
            widget = Editor(item)
        elif item.path.suffix.lower() in SUPPORTED_CHUNK_FILE_FORMATS:
            widget = ChunkedObjView(item)
        elif item.path.suffix.lower() in SUPPORTED_IMG_FORMATS:
            widget = QImageViewer.fromFile(item.contents())

        if widget is not None:
            self.starfab.add_tab_widget(item.path, widget, item.path.name)


class StarFabStaticWidget(qtw.QWidget):
    __ui_file__ = None

    closing = qtc.Signal()

    def __init__(self, starfab=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.__ui_file__ is not None:
            uic.loadUi(self.__ui_file__, self)
        sizePolicy = qtw.QSizePolicy(
            qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(2)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)

        self.starfab = starfab or get_starfab()
        self.ctx_manager = StarFabContextMenuManager()
        self.ctx_manager.action_triggered.connect(self._on_ctx_triggered)
        self._ctx_item = None

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        pass

    def _handle_item_action(self, item, model, index):
        widget = None

        # refactor to avoid the circular import
        from starfab.gui.widgets.object_container_viewer import ObjectContainerView, \
            SUPPORTED_OBJECT_CONTAINER_FILE_FORMATS

        if isinstance(item, dict):
            # TODO: this needs be handled much better than "is it a dict" -.-'
            widget = DDSImageViewer(item)
            item = widget.dds_header
        elif item.path.suffix.lower() in SUPPORTED_EDITOR_FORMATS:
            widget = Editor(item)
        elif item.path.suffix.lower() in SUPPORTED_CHUNK_FILE_FORMATS:
            widget = ChunkedObjView(item)
        elif item.path.suffix.lower() in SUPPORTED_IMG_FORMATS:
            widget = QImageViewer.fromFile(item.contents())
        elif item.path.suffix.lower() in SUPPORTED_OBJECT_CONTAINER_FILE_FORMATS:
            widget = ObjectContainerView(item)

        if widget is not None:
            self.starfab.add_tab_widget(item.path, widget, item.path.name)


class StarFabSearchableTreeFilterWidget(qtw.QWidget):
    filter_changed = qtc.Signal()
    remove_filter = qtc.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def compile_filter(self) -> (typing.Callable, typing.Callable):
        return operator.and_, lambda i: True

    def close_filter(self):
        self.remove_filter.emit()


class StarFabSearchableTreeDockWidget(StarFabDockWidget):
    __ui_file__ = str(RES_PATH / "ui" / "FileViewDock.ui")

    def __init__(self, starfab, proxy_model=None, *args, **kwargs):
        super().__init__(starfab, *args, **kwargs)

        self.sc_breadcrumbs.setVisible(False)
        self.sc_breadcrumbs.linkActivated.connect(self._handle_breadcrumbs)

        tree_header = self.sc_tree.header()
        tree_header.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        tree_header.customContextMenuRequested.connect(self._show_header_ctx_menu)

        self.sc_tree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tree.customContextMenuRequested.connect(self._show_ctx_menu)
        self.sc_tree.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.sc_tree.setSortingEnabled(True)

        self.sc_add_filter.clicked.connect(self._handle_add_filter)
        self.sc_add_filter.setIcon(qta.icon("mdi.filter"))
        self.sc_add_filter.hide()

        self.sc_tree_search.editingFinished.connect(self._handle_search_changed)
        self.sc_search.setIcon(qta.icon("mdi6.text-search"))
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
        self.proxy_model.setAdditionFilters(
            [
                cf
                for i in range(fl.count())
                if (cf := fl.itemAt(i).widget().compile_filter()) is not None
            ]
        )

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
    def _show_header_ctx_menu(self, pos):
        menu = qtw.QMenu()
        menu.exec_(self.sc_tree.header().mapToGlobal(pos))

    @qtc.Slot(qtc.QPoint)
    def _show_ctx_menu(self, pos):
        self._ctx_item = self.sc_tree.indexAt(pos)
        try:
            if isinstance(self.sc_tree_model, qtw.QFileSystemModel):
                path = self.sc_tree_model.filePath(
                    self.proxy_model.mapToSource(self._ctx_item)
                )
            else:
                path = self.sc_tree_model.itemFromIndex(
                    self.proxy_model.mapToSource(self._ctx_item)
                ).path
        except Exception as e:
            path = ""
        menu = self.ctx_manager.menu_for_path(path)
        menu.exec_(self.sc_tree.mapToGlobal(pos))

    def get_selected_items(self):
        selected_items = []

        def _add_indexes(indexes):
            for i in indexes:
                if self.proxy_model.hasChildren(i):
                    children = [
                        self.proxy_model.index(_, 0, i)
                        for _ in range(0, self.proxy_model.rowCount(i))
                    ]
                    _add_indexes(children)
                else:
                    selected_items.append(
                        self.proxy_model.mapToSource(i).internalPointer()
                    )

        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        if not selection and self._ctx_item is not None:
            selection = [self._ctx_item]

        _add_indexes(selection)
        return selected_items

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        if action == "collapse_all":
            self.sc_tree.collapseAll()
            return []
        elif action == "doubleclick":
            return (
                self._on_doubleclick(self._ctx_item)
                if self._ctx_item is not None
                else None
            )
        elif action == "expand_all":
            selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
            if not selection and self._ctx_item is not None:
                selection = [self._ctx_item]
            for index in selection:
                self.sc_tree.expandRecursively(index)
            return []
        return self.get_selected_items()

    @qtc.Slot(str)
    def _handle_search_changed(self):
        self.proxy_model.setFilterText(self.sc_tree_search.text())

    def deleteLater(self):
        self.closing.emit()
        super().deleteLater()


class StarFabSearchableTreeWidget(StarFabStaticWidget):
    __ui_file__ = str(RES_PATH / "ui" / "FileView.ui")

    def __init__(self, proxy_model=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.sc_breadcrumbs.setVisible(False)
        self.sc_breadcrumbs.linkActivated.connect(self._handle_breadcrumbs)

        tree_header = self.sc_tree.header()
        tree_header.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        tree_header.customContextMenuRequested.connect(self._show_header_ctx_menu)

        self.sc_tree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.sc_tree.setUniformRowHeights(True)
        self.sc_tree.customContextMenuRequested.connect(self._show_ctx_menu)
        self.sc_tree.setSelectionMode(qtw.QAbstractItemView.ExtendedSelection)
        self.sc_tree.setSortingEnabled(True)

        self.sc_add_filter.clicked.connect(self._handle_add_filter)
        self.sc_add_filter.setIcon(qta.icon("mdi.filter"))
        self.sc_add_filter.hide()

        self.sc_tree_search.editingFinished.connect(self._handle_search_changed)
        self.sc_search.setIcon(qta.icon("mdi6.text-search"))
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

    def _sync_tree_header(self):
        settings.beginGroup(f'{self.__class__.__name__}/sc_tree/show_header')
        try:
            for col in settings.childKeys():
                try:
                    self.sc_tree.setColumnHidden(int(col), parsebool(settings.value(col)))
                except Exception as e:
                    logger.exception(f'Bad key in settings for header preferences', exc_info=e)
                    settings.remove(col)
        finally:
            settings.endGroup()

    def _filters_changed(self):
        fl = self.filter_widgets.layout()
        self.proxy_model.setAdditionFilters(
            [
                cf
                for i in range(fl.count())
                if (cf := fl.itemAt(i).widget().compile_filter()) is not None
            ]
        )

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

    def _handle_header_toggled(self, checked):
        col = self.sender().column
        self.sc_tree.setColumnHidden(col, not checked)
        settings.setValue(f'{self.__class__.__name__}/sc_tree/show_header/{col}', not checked)

    @qtc.Slot(qtc.QPoint)
    def _show_header_ctx_menu(self, pos):
        if self.sc_tree_model is None:
            return
        menu = qtw.QMenu()
        for i in range(1, self.sc_tree_model.columnCount(None)):
            action = menu.addAction(self.sc_tree_model.headerData(i, qtc.Qt.Horizontal, qtc.Qt.DisplayRole))
            action.column = i
            action.setCheckable(True)
            action.setChecked(not self.sc_tree.isColumnHidden(i))
            action.triggered.connect(self._handle_header_toggled)
        menu.exec_(self.sc_tree.header().mapToGlobal(pos))

    @qtc.Slot(qtc.QPoint)
    def _show_ctx_menu(self, pos):
        self._ctx_item = self.sc_tree.indexAt(pos)
        try:
            if isinstance(self.sc_tree_model, qtw.QFileSystemModel):
                path = self.sc_tree_model.filePath(
                    self.proxy_model.mapToSource(self._ctx_item)
                )
            else:
                path = self.sc_tree_model.itemFromIndex(
                    self.proxy_model.mapToSource(self._ctx_item)
                ).path
        except Exception as e:
            path = ""
        menu = self.ctx_manager.menu_for_path(path)
        menu.exec_(self.sc_tree.mapToGlobal(pos))

    def get_selected_items(self):
        selected_items = []

        def _add_indexes(indexes):
            for i in indexes:
                if self.proxy_model.hasChildren(i):
                    children = [
                        self.proxy_model.index(_, 0, i)
                        for _ in range(0, self.proxy_model.rowCount(i))
                    ]
                    _add_indexes(children)
                else:
                    selected_items.append(
                        self.proxy_model.mapToSource(i).internalPointer()
                    )

        selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
        if not selection and self._ctx_item is not None:
            selection = [self._ctx_item]

        _add_indexes(selection)
        return selected_items

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        if action == "collapse_all":
            self.sc_tree.collapseAll()
            return []
        elif action == "doubleclick":
            return (
                self._on_doubleclick(self._ctx_item)
                if self._ctx_item is not None
                else None
            )
        elif action == "expand_all":
            selection = [_ for _ in self.sc_tree.selectedIndexes() if _.column() == 0]
            if not selection and self._ctx_item is not None:
                selection = [self._ctx_item]
            for index in selection:
                self.sc_tree.expandRecursively(index)
            return []
        return self.get_selected_items()

    @qtc.Slot(str)
    def _handle_search_changed(self):
        self.proxy_model.setFilterText(self.sc_tree_search.text())

    def deleteLater(self):
        self.closing.emit()
        super().deleteLater()