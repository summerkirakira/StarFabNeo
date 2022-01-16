import os
import shutil
from pathlib import Path
from functools import partial

from starfab.gui import qtc, qtw, qtg

from starfab.models.common import AudioConverter
from starfab.gui.utils import ScrollMessageBox
from starfab.gui.dialogs.export_dialog import P4KExportDialog
from starfab.gui.widgets.dock_widgets.common import StarFabSearchableTreeWidget
from starfab.models.p4k import P4KSortFilterProxyModelArchive
from starfab.utils import show_file_in_filemanager
from starfab.log import getLogger

logger = getLogger(__name__)
P4KWIDGET_COLUMNS = ['Name', 'Size', 'Kind', 'Date Modified']


class P4KView(StarFabSearchableTreeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=P4KSortFilterProxyModelArchive, *args, **kwargs)
        self.setWindowTitle(self.tr('Data.p4k'))

        self.sc_tree_model = self.starfab.sc_manager.p4k_model
        self.starfab.sc_manager.p4k_model.loaded.connect(self._handle_p4k_loaded)

        self.ctx_manager.default_menu.addSeparator()
        save_file = self.ctx_manager.menus[''].addAction('Save To...')
        save_file.triggered.connect(partial(self.ctx_manager.handle_action, 'save_to'))
        extract = self.ctx_manager.menus[''].addAction('Extract to...')
        extract.triggered.connect(partial(self.ctx_manager.handle_action, 'extract'))
        copy_path = self.ctx_manager.menus[''].addAction('Copy Path')
        copy_path.triggered.connect(partial(self.ctx_manager.handle_action, 'copy_path'))

        wem_menu = self.ctx_manager.menus['.wem'] = qtw.QMenu()
        convert_wem = wem_menu.addAction('Convert wem')
        convert_wem.triggered.connect(partial(self.ctx_manager.handle_action, 'convert_wem'))

        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = super()._on_ctx_triggered(action)

        # Item Actions
        if not selected_items:
            return

        if action == 'extract':
            export_dlg = P4KExportDialog(selected_items)
            export_dlg.exec_()
        elif action == 'save_to':
            export_dlg = P4KExportDialog(selected_items, save_to=True)
            export_dlg.exec_()
        elif action == 'copy_path':
            qtg.QGuiApplication.clipboard().setText(selected_items[0].path.as_posix())
        elif action == 'convert_wem':
            edir = qtw.QFileDialog.getExistingDirectory(self.starfab, 'Save To...')
            if edir:
                edir = Path(edir)
                total = len(selected_items)
                self.starfab.task_started.emit('convert_wem', f'Converting to {edir}', 0, total)
                for i, item in enumerate(selected_items):
                    if item.path.suffix != '.wem':
                        continue
                    self.starfab.update_status_progress.emit('convert_wem', 1, 0, total,
                                                             f'Converting {item.path.name} to {edir}')
                    try:
                        result = AudioConverter(item.path.stem).run()
                        if result['ogg']:
                            shutil.move(result['ogg'], edir / f'{item.path.name}.ogg')
                    except Exception as e:
                        logger.exception(f'Failed to convert wem {item.path}', exc_info=e)

                self.starfab.task_finished.emit('convert_wem', True, '')
                show_file_in_filemanager(Path(edir))

    def _on_doubleclick(self, index):
        if not index.isValid():
            return

        item = self.proxy_model.mapToSource(index).internalPointer()
        try:
            if item is not None:
                if '.dds' in item.name:
                    basename = f'{item.name.split(".dds")[0]}.dds'
                    items = [_ for _ in item.parent.children if _.path.name.startswith(basename)]
                    self._handle_item_action({i.path.as_posix(): i for i in items}, self.sc_tree_model, index)
                elif item.suffix == '.wem':
                    self.starfab.play_wem(item.path.stem)
                elif item.suffix.lower() == '.dcb':
                    self.starfab.show_dcb_view()
                else:
                    self._handle_item_action(item, self.sc_tree_model, index)
        except Exception as e:
            ScrollMessageBox.critical(self, "Error opening file", f"{e}")

    def _handle_p4k_loaded(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, qtw.QHeaderView.Stretch)
        self.sc_tree.hideColumn(4)
