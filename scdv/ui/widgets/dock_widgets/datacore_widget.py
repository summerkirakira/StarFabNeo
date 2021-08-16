import io
import os
import time
import shutil
import logging
import typing
import operator
from pathlib import Path
from functools import partial, cached_property

from scdatatools.forge.dftypes import StructureInstance

from scdv import get_scdv
from scdv.ui import qtc, qtw, qtg
from scdv.ui.utils import icon_provider
from scdv.ui.widgets.dcbrecord import DCBRecordItemView
from scdv.ui.common import PathArchiveTreeModel, PathArchiveTreeModelLoader, PathArchiveTreeItem, \
    PathArchiveTreeSortFilterProxyModel, ContentItem
from scdv.ui.widgets.common import TagBar
from scdv.utils import show_file_in_filemanager, reload_scdv_modules
from scdv.ui.widgets.dock_widgets.common import SCDVSearchableTreeDockWidget, SCDVSearchableTreeFilterWidget

logger = logging.getLogger(__name__)

DCBVIEW_COLUMNS = ['Name', 'Type']

RECORDS_ROOT_PATH = 'libs/foundry/records/'


class DCBSortFilterProxyModel(PathArchiveTreeSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent: qtc.QModelIndex) -> bool:
        if not self._filter and not self.additional_filters:
            return True

        if parent := source_parent.internalPointer():
            try:
                item = parent.children[source_row]
            except IndexError:
                return False
            if not self.checkAdditionFilters(item):
                return False
            if not self._filter and item.record is not None:
                return True   # additional filters true and not a folder
            if self._filter:
                if self.filterCaseSensitivity() == qtc.Qt.CaseInsensitive:
                    return self._filter.lower() in item._path.lower() or self._filter.lower() in item.guid
                else:
                    return self._filter in item._path or self._filter in item.guid
        return False


class DCBTreeModel(PathArchiveTreeModel):
    def __init__(self, archive, columns=None, item_cls=None, parent=None):
        super().__init__(archive=archive, columns=columns, item_cls=item_cls, parent=parent)
        self._guid_cache = {}

    def itemForGUID(self, guid):
        return self._guid_cache.get(guid)


class DCBTreeLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        return self.model.archive.records

    def load_item(self, item):
        path = item.filename.replace(RECORDS_ROOT_PATH, '')
        parent_path, name = path.rsplit('/', maxsplit=1) if '/' in path else ('', path)
        parent = self.model.parentForPath(parent_path)
        name = name.replace('.xml', '')
        if name in parent.children_by_name:
            name = f'{name}.{item.id.value}'

        new_item = self._item_cls(parent_path + '/' + name, model=self.model, record=item, parent=parent)
        self.model._guid_cache[new_item.guid] = new_item


class DCBTreeItem(PathArchiveTreeItem, ContentItem):
    _cached_properties_ = PathArchiveTreeItem._cached_properties_ + ['guid', 'type']

    def __init__(self, path,  model, record=None, parent=None):
        super().__init__(path, model, parent)
        self.record = record

    @cached_property
    def icon(self):
        if self.children:
            return icon_provider.icon(icon_provider.Folder)
        return icon_provider.icon(icon_provider.File)

    @cached_property
    def guid(self):
        if self.record is not None:
            return self.record.id.value
        return ''

    @cached_property
    def type(self):
        if self.record is not None:
            return self.record.type
        return ''

    def contents(self, mode=None):
        if self.guid is not None:
            mode = mode if mode is not None else get_scdv().settings.value('cryxmlbConversionFormat', 'xml')
            if mode == 'xml':
                return io.BytesIO(
                    self.model.archive.dump_record_xml(self.model.archive.records_by_guid[self.guid]).encode('utf-8')
                )
            return io.BytesIO(
                self.model.archive.dump_record_json(self.model.archive.records_by_guid[self.guid]).encode('utf-8')
            )
        return io.BytesIO(b'')

    def data(self, column, role):
        if role == qtc.Qt.DisplayRole:
            if column == 0:
                return self.name
            elif column == 1:
                return self.type
            elif column == 2:
                return self.guid
            else:
                return ''
        return super().data(column, role)

    def __repr__(self):
        return f'<DCBTreeItem {self.name} [{self.guid}] "{self._path}">'


def _filter_tags(item, method, tags, tdb):
    if item.record is None:
        return False
    tags_to_check = set()
    item_tags = item.record.properties.get('tags', [])
    if isinstance(item_tags, StructureInstance):
        tags_to_check.update(
            str(tag) for _ in item_tags.properties.values() if (tag := tdb.tags_by_guid.get(str(_)) is not None)
        )
    else:
        tags_to_check.update(str(tag) for _ in item_tags if (tag := tdb.tags_by_guid.get(_.name)) is not None)
    return method(tag in tags for tag in tags_to_check)


class DCBFilterWidget(SCDVSearchableTreeFilterWidget):
    filter_types = {
        'has_any_tag': 'Has Any Tag',
        'has_all_tags': 'Has All Tags',
        'type': 'Type'
    }

    filter_operators = {
        'and_': 'And',
        'or_': 'Or',
        'not_': 'Not',
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.h_layout = qtw.QHBoxLayout()
        self.setLayout(self.h_layout)
        self.setContentsMargins(1, 1, 1, 1)
        self.h_layout.setContentsMargins(1, 1, 1, 1)

        self.filter_op = qtw.QComboBox()
        for k, v in self.filter_operators.items():
            self.filter_op.addItem(v, userData=k)
        self.filter_op.currentIndexChanged.connect(self._handle_filter_updated)
        self.filter_op.setSizePolicy(qtw.QSizePolicy.Minimum, qtw.QSizePolicy.Minimum)
        self.filter_op.setFixedWidth(48)
        self.h_layout.addWidget(self.filter_op)

        self.filter_type = qtw.QComboBox()
        for k, v in self.filter_types.items():
            self.filter_type.addItem(v, userData=k)
        self.filter_type.currentIndexChanged.connect(self._handle_filter_type_changed)
        self.filter_type.setSizePolicy(qtw.QSizePolicy.Minimum, qtw.QSizePolicy.Minimum)
        self.filter_type.setFixedWidth(100)
        self.h_layout.addWidget(self.filter_type)

        self.tagbar = TagBar(self)
        self.tagbar.tags_updated.connect(self._handle_filter_updated)
        self.h_layout.addWidget(self.tagbar)

        scdv = get_scdv()
        if scdv.sc is not None:
            self._tag_completer = qtw.QCompleter(scdv.sc.tag_database.tag_names())
            self._tag_completer.setCaseSensitivity(qtc.Qt.CaseInsensitive)
            self._tag_completer.setFilterMode(qtc.Qt.MatchEndsWith)
            self._type_completer = qtw.QCompleter(sorted(scdv.sc.datacore.record_types))
            self._type_completer.setCaseSensitivity(qtc.Qt.CaseInsensitive)
            self._type_completer.setFilterMode(qtc.Qt.MatchStartsWith)

        close_btn = qtw.QPushButton('-')
        close_btn.setFixedSize(24, 24)
        close_btn.setSizePolicy(qtw.QSizePolicy.Maximum, qtw.QSizePolicy.Maximum)
        close_btn.clicked.connect(self.close_filter)
        self.h_layout.addWidget(close_btn)

        self._handle_filter_type_changed(None)
        self.show()

    def compile_filter(self) -> (typing.Callable, typing.Callable):
        filter_type = self.filter_type.currentData()
        op = getattr(operator, self.filter_op.currentData())
        scdv = get_scdv()
        if not self.tagbar.tags or scdv.sc is None:
            return None
        elif filter_type == 'has_any_tag':
            return op, partial(_filter_tags, method=any, tags=self.tagbar.tags, tdb=scdv.sc.tag_database)
        elif filter_type == 'has_all_tags':
            return op, partial(_filter_tags, method=all, tags=self.tagbar.tags, tdb=scdv.sc.tag_database)
        elif filter_type == 'type':
            return op, lambda i, ts=self.tagbar.tags: i.record is not None and i.record.type in ts

    def _handle_filter_updated(self):
        self.filter_changed.emit()

    def _handle_filter_type_changed(self, index):
        filter_type = self.filter_type.currentData()
        self.tagbar.clear()
        if filter_type in ['has_any_tag', 'has_all_tags']:
            self.tagbar.valid_tags = get_scdv().sc.tag_database.tag_names()
            self.tagbar.line_edit.setCompleter(self._tag_completer)
        elif filter_type == 'type':
            self.tagbar.valid_tags = list(get_scdv().sc.datacore.record_types)
            self.tagbar.line_edit.setCompleter(self._type_completer)
        self.filter_changed.emit()


class DCBViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=DCBSortFilterProxyModel, *args, **kwargs)
        self.setWindowTitle(self.tr('DataCore'))
        self.scdv.p4k_loaded.connect(self.handle_datacore_opened)
        self.proxy_model.setFilterKeyColumn(3)

        self.ctx_manager.default_menu.addSeparator()
        extract = self.ctx_manager.default_menu.addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        extract = self.ctx_manager.menus[''].addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        extract_all = self.ctx_manager.menus[''].addAction('Extract All...')
        extract_all.triggered.connect(partial(self.ctx_manager.handle_action, 'extract_all'))

        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)

        self.sc_add_filter.show()
        self.handle_datacore_opened()

    def _create_filter(self):
        return DCBFilterWidget(self)

    @qtc.Slot()
    def _finished_loading(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.raise_()
        self.scdv.datacore_loaded.emit()

    def handle_datacore_opened(self):
        if self.scdv.sc is not None and self.scdv.sc.is_loaded('datacore'):
            self.show()
            self.sc_tree_model = DCBTreeModel(archive=self.scdv.sc.datacore, columns=DCBVIEW_COLUMNS,
                                              item_cls=DCBTreeItem, parent=self)
            loader = DCBTreeLoader(self.scdv, self.sc_tree_model, item_cls=DCBTreeItem,
                                   task_name='load_dcb_view', task_status_msg='Processing DataCore')
            self.closing.connect(lambda: loader.signals.cancel.emit())
            loader.signals.finished.connect(self._finished_loading)
            qtc.QThreadPool.globalInstance().start(loader)

    def _handle_item_action(self, item, model, index):
        if os.environ.get('SCDV_RELOAD_MODULES'):
            reload_scdv_modules('scdv.ui.widgets.dcbrecord')
            reload_scdv_modules('scdv.ui.widgets.common')
        if isinstance(item, DCBTreeItem) and item.record is not None:
            widget = DCBRecordItemView(item, self.scdv)
            self.scdv.add_tab_widget(item.path, widget, item.name, tooltip=item.path.as_posix())
            # TODO: error dialog

    def extract_items(self, items):
        items = [i for i in items if i.guid]
        edir = Path(qtw.QFileDialog.getExistingDirectory(self.scdv, 'Extract to...'))
        if edir:
            total = len(items)
            self.scdv.task_started.emit('extract_dcb', f'Extracting to {edir.name}', 0, total)
            t = time.time()
            for i, item in enumerate(items):
                if (time.time() - t) > 0.5:
                    self.scdv.update_status_progress.emit('extract_dcb', i, 0, total,
                                                          f'Extracting records to {edir.name}')
                    t = time.time()
                try:
                    outfile = edir / item.path
                    outfile.parent.mkdir(parents=True, exist_ok=True)
                    if outfile.is_file():
                        outfile = outfile.parent / f'{outfile.stem}.{item.guid}{outfile.suffix}'
                    with outfile.open('wb') as o:
                        shutil.copyfileobj(item.contents(), o)
                    qtg.QGuiApplication.processEvents()
                except Exception as e:
                    logger.exception(f'Exception extracting record {item.path}', exc_info=e)

            self.scdv.task_finished.emit('extract_dcb', True, '')
            show_file_in_filemanager(Path(edir))

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        if action == 'extract':
            selected_items = self.get_selected_items()
            # Item Actions
            if not selected_items:
                return
            self.extract_items(selected_items)
        elif action == 'extract_all':
            self.extract_items(self.sc_tree_model._guid_cache.values())
        else:
            return super()._on_ctx_triggered(action)
