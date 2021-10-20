import io
import os
import shutil
import logging
from pathlib import Path
from functools import partial, cached_property

from scdv.ui import qtc, qtw

from scdatatools.cry.cryxml import pprint_xml_tree, etree_from_cryxml_file, is_cryxmlb_file
from scdv.ui.common import PathArchiveTreeSortFilterProxyModel, PathArchiveTreeItem, PathArchiveTreeModel, \
    AudioConverter, \
    PathArchiveTreeModelLoader, ContentItem
from scdv.ui.utils import ScrollMessageBox
from scdv.ui.widgets.dock_widgets.common import SCDVSearchableTreeDockWidget
from scdv.utils import show_file_in_filemanager

logger = logging.getLogger(__name__)
P4KWIDGET_COLUMNS = ['Name', 'Size', 'Kind', 'Date Modified']


class P4KViewDock(SCDVSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=P4KSortFilterProxyModelArchive, *args, **kwargs)
        self.setWindowTitle(self.tr('Data.p4k'))
        self.scdv.opened.connect(self.handle_sc_opened)

        self.ctx_manager.default_menu.addSeparator()
        save_file = self.ctx_manager.default_menu.addAction('Save To...')
        save_file.triggered.connect(partial(self.ctx_manager.handle_action, 'save_to'))
        extract = self.ctx_manager.default_menu.addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        extract = self.ctx_manager.menus[''].addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))

        wem_menu = self.ctx_manager.menus['.wem'] = qtw.QMenu()
        convert_wem = wem_menu.addAction('Convert wem')
        convert_wem.triggered.connect(partial(self.ctx_manager.handle_action, 'convert_wem'))

        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)

        self.handle_sc_opened()

    @qtc.Slot(str)
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
                self.scdv.task_started.emit('extract', f'Extracting to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    self.scdv.update_status_progress.emit('extract', 1, 0, total,
                                                          f'Extracting {item.path.name} to {edir}')
                    try:
                        item.extract_to(edir)
                    except Exception as e:
                        logger.exception(f'Exception while extraction', exc_info=e)

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
                        logger.exception(exc_info=e)

                self.scdv.task_finished.emit('extract', True, '')
                show_file_in_filemanager(Path(edir))
        elif action == 'convert_wem':
            edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Save To...')
            if edir:
                edir = Path(edir)
                total = len(selected_items)
                self.scdv.task_started.emit('convert_wem', f'Converting to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    if item.path.suffix != '.wem':
                        continue
                    self.scdv.update_status_progress.emit('convert_wem', 1, 0, total,
                                                          f'Converting {item.path.name} to {edir}')
                    try:
                        result = AudioConverter(item.path.stem).run()
                        if result['ogg']:
                            shutil.move(result['ogg'], edir / f'{item.path.name}.ogg')
                    except Exception as e:
                        logger.exception(f'Failed to convert wem {item.path}', exc_info=e)

                self.scdv.task_finished.emit('convert_wem', True, '')
                show_file_in_filemanager(Path(edir))

    def _finished_loading(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.sc_tree.hideColumn(4)
        self.raise_()

    def handle_sc_opened(self):
        if self.scdv.sc is not None:
            self.show()
            self.sc_tree_model = PathArchiveTreeModel(archive=self.scdv.sc.p4k, columns=P4KWIDGET_COLUMNS,
                                                      item_cls=P4KTreeItem, parent=self)
            loader = P4KTreeLoader(self.scdv, self.sc_tree_model, item_cls=P4KTreeItem,
                                   task_name='load_p4k_view', task_status_msg='Processing Data.p4k',
                                   load_limit= int(os.environ.get('SCDV_P4K_LIMIT', -1)))
            self.closing.connect(lambda: loader.signals.cancel.emit())
            loader.signals.finished.connect(self._finished_loading)
            qtc.QThreadPool.globalInstance().start(loader)

    def _on_doubleclick(self, index):
        if not index.isValid():
            return

        item = self.proxy_model.mapToSource(index).internalPointer()
        try:
            if item is not None:
                if '.dds' in item.name:
                    basename = f'{item.name.split(".dds")[0]}.dds'
                    items = sorted([_ for _ in item.parent.children if _.path.name.startswith(basename)],
                                   key=lambda item: item.path.as_posix())

                    self._handle_item_action({items[0].path.as_posix(): items}, self.sc_tree_model, index)
                elif item.suffix == '.wem':
                    self.scdv.play_wem(item.path.stem)
                else:
                    self._handle_item_action(item, self.sc_tree_model, index)
        except Exception as e:
            ScrollMessageBox.critical(self, "Error opening file", f"{e}")


class P4KSortFilterProxyModelArchive(PathArchiveTreeSortFilterProxyModel):
    def lessThan(self, source_left, source_right):
        if self.sortColumn() in [1, 3]:
            return (self.sourceModel().data(source_left, qtc.Qt.UserRole) <
                    self.sourceModel().data(source_right, qtc.Qt.UserRole))
        else:
            return super().lessThan(source_left, source_right)


class P4KTreeItem(PathArchiveTreeItem, ContentItem):
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
        if os.environ.get('SCDV_QUICK'):
            return ''
        if self.raw_size is not None:
            return qtc.QLocale().formattedDataSize(self.raw_size)
        return ''

    @cached_property
    def date_modified(self):
        if os.environ.get('SCDV_QUICK'):
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


class P4KTreeLoader(PathArchiveTreeModelLoader):
    def items_to_load(self):
        return self.model.archive.filelist

    def load_item(self, item):
        self._item_cls(item.filename, model=self.model, parent=self.model.parentForPath(item.filename))
