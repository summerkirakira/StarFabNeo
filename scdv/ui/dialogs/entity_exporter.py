import shutil
from pathlib import Path
from functools import partial
from datetime import datetime
from distutils.util import strtobool

from qtpy import uic
from qtpy.QtCore import Slot

from scdatatools.sc.utils import extract_entity, CGF_CONVERTER_MODEL_EXTS

from scdv.ui import qtg, qtw, qtc
from scdv.resources import RES_PATH
from scdv.settings import get_cgf_converter
from scdv.ui.widgets.dock_widgets.audio import WW2OGG, REVORB
from scdv.utils import show_file_in_filemanager, image_converter

DATACORE_RELATIVE_BASE = Path('libs/foundry/records/')
SHIP_ENTITIES_PATH = 'libs/foundry/records/entities/spaceships'
VEHICLE_ENTITIES_PATH = 'libs/foundry/records/entities/groundvehicles'


class EntityExportLog(qtw.QDialog):
    def __init__(self, scdv, outdir, entities, create_entity_dir=True, output_model_log=False, export_options=None):
        super().__init__(parent=scdv)
        self.setMinimumSize(1024, 800)
        self.scdv = scdv
        self.export_options = export_options or {}
        self.create_entity_dir = create_entity_dir
        self.output_model_log = output_model_log

        self.output_tabs = qtw.QTabWidget()
        self.output_tabs.setTabsClosable(False)
        self.setSizeGripEnabled(True)

        self.closebtn = qtw.QDialogButtonBox()
        self.closebtn.setOrientation(qtc.Qt.Horizontal)
        self.closebtn.setStandardButtons(qtw.QDialogButtonBox.Ok)
        self.closebtn.setEnabled(False)
        self.closebtn.clicked.connect(self.close)

        layout = qtw.QVBoxLayout()
        layout.addWidget(self.output_tabs)
        layout.addWidget(self.closebtn)
        self.setLayout(layout)

        self.entities = entities
        self.outdir = Path(outdir)

    def closeEvent(self, event) -> None:
        if self.closebtn.isEnabled():
            event.accept()
        else:
            event.ignore()

    def _output_monitor(self, msg, entity, console, default_fmt, log_file, model_log_file, overview_console):
        fmt = qtg.QTextCharFormat()
        overview_out = False
        if 'WARN' in msg:
            fmt.setFontWeight(qtg.QFont.Bold)
            fmt.setForeground(qtg.QColor("#f5ad42"))
            overview_out = True
        elif 'ERROR' in msg:
            fmt.setFontWeight(qtg.QFont.Bold)
            fmt.setForeground(qtg.QColor("#ff4d4d"))
            overview_out = True
        else:
            fmt = default_fmt
        console.setCurrentCharFormat(fmt)
        console.append(f'{msg}')
        if overview_out:
            overview_console.setCurrentCharFormat(fmt)
            overview_console.append(f'{entity}: {msg}')
        log_file.write(f'{msg}\n')
        if (model_log_file and msg.startswith('zstd |') and
                any(msg.lower().endswith(_) for _ in CGF_CONVERTER_MODEL_EXTS)):
            model_log_file.write(f"{msg.split(' | ')[-1]}\n")
        qtg.QGuiApplication.processEvents()

    def extract_entities(self) -> None:
        overview_tab = qtw.QWidget()
        layout = qtw.QVBoxLayout()
        overview_console = qtw.QTextEdit(overview_tab)
        overview_console.setReadOnly(True)
        default_fmt = overview_console.currentCharFormat()
        layout.addWidget(overview_console)
        overview_tab.setLayout(layout)
        self.output_tabs.addTab(overview_tab, 'Overview')
        self.output_tabs.setCurrentWidget(overview_tab)

        overview_console.append('Export Overview')
        overview_console.append('-' * 80)

        start = datetime.now()
        for i, entity in enumerate(self.entities):
            model_log = ''
            try:
                tab = qtw.QWidget()
                layout = qtw.QVBoxLayout()
                console = qtw.QTextEdit(tab)
                console.setReadOnly(True)
                layout.addWidget(console)
                tab.setLayout(layout)
                self.output_tabs.addTab(tab, entity.name)
                self.output_tabs.setCurrentWidget(tab)

                self.setWindowTitle(f'Extracting Entity {i + 1}/{len(self.entities)}: {entity.name} ({entity.id})')
                entity_output_dir = self.outdir / entity.name if self.create_entity_dir else self.outdir
                logfile = entity_output_dir / f'{datetime.now().strftime("%Y_%m_%d-%H_%M_%S")}_{entity.name}.extraction.log'
                logfile.parent.mkdir(parents=True, exist_ok=True)

                if self.output_model_log:
                    model_log = (entity_output_dir / f'{datetime.now().strftime("%Y_%m_%d-%H_%M_%S")}_{entity.name}'
                                                     f'.extracted_models.log').open('w')

                with logfile.open('w') as log:
                    extract_entity(self.scdv.sc, entity.id, outdir=entity_output_dir,
                                   monitor=partial(self._output_monitor, console=console, entity=entity.name,
                                                   default_fmt=default_fmt, log_file=log, model_log_file=model_log,
                                                   overview_console=overview_console),
                                   **self.export_options
                                   )
            except Exception as e:
                print(f'ERROR EXTRACTING SHIP {entity}: {e}')
            finally:
                if model_log:
                    model_log.close()

        overview_console.setCurrentCharFormat(default_fmt)
        overview_console.append('-' * 80)
        overview_console.append(f'\n\nFinished exporting {len(self.entities)} entitys in {datetime.now() - start}')
        overview_console.append(f'Output directory: {self.outdir}')
        self.output_tabs.setCurrentWidget(overview_tab)
        show_file_in_filemanager(Path(self.outdir))
        self.closebtn.setEnabled(True)


class EntityExporterDialog(qtw.QDialog):
    def __init__(self, scdv, entities_to_extract=None):
        super().__init__(parent=None)
        entities_to_extract = entities_to_extract or []
        self.scdv = scdv
        uic.loadUi(str(RES_PATH / 'ui' / 'EntityExportDialog.ui'), self)  # Load the ui into self

        self.buttonBox.accepted.connect(self.handle_extract)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.button(qtw.QDialogButtonBox.Save).setText("Export")
        self.deselectAllButton.clicked.connect(self.deselect_all)
        self.selectAllButton.clicked.connect(self.select_all)

        self.listFilter.textChanged.connect(self.on_filter_text_changed)
        self.entityTree.itemDoubleClicked.connect(self.on_item_doubleclick)
        self.entityTree.setColumnCount(1)
        self.entityTree.setHeaderHidden(True)
        self.entityTree.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.entityTree.customContextMenuRequested.connect(self._show_ctx_menu)

        self.ctx_menu = qtw.QMenu()
        expand_all = self.ctx_menu.addAction('Expand All')
        expand_all.triggered.connect(self._expand_all)
        collapse_all = self.ctx_menu.addAction('Collapse All')
        collapse_all.triggered.connect(self._collapse_all)

        open_dir_icon = qtw.QApplication.style().standardIcon(qtw.QStyle.SP_DirIcon)
        self.tree_folders = {}

        self.entities = {}

        def get_or_create_parent(path):
            if str(path) == '.':
                return self.entityTree.invisibleRootItem()
            elif path.as_posix() not in self.tree_folders:
                p = get_or_create_parent(path.parent)
                new_par = qtw.QTreeWidgetItem(p)
                new_par.setText(0, path.name)
                new_par.setIcon(0, open_dir_icon)
                self.tree_folders[path.as_posix()] = new_par
            return self.tree_folders.get(path.as_posix())

        if self.scdv.sc is not None:
            # self.entities = {
            #     s.name: s for s in self.scdv.sc.datacore.search_filename(f'{SHIP_ENTITIES_PATH}/*')
            # }
            # self.entities.update({
            #     v.name: v for v in self.scdv.sc.datacore.search_filename(f'{VEHICLE_ENTITIES_PATH}/*')
            # })
            entities = {_.filename: _ for _ in self.scdv.sc.datacore.records if _.type == 'EntityClassDefinition'}
            for entity in sorted(entities.keys()):
                entity = entities[entity]
                if (entity.type != 'EntityClassDefinition' or
                        not [_ for _ in entity.properties.get('Components', [])
                             if _.name == 'SGeometryResourceParams']):
                    continue
                parent = get_or_create_parent(Path(entity.filename).relative_to(DATACORE_RELATIVE_BASE).parent)
                if parent is not None:
                    entity_item = qtw.QTreeWidgetItem(parent)
                    entity_item.setText(0, entity.name)
                    entity_item.setFlags(entity_item.flags() | qtc.Qt.ItemIsUserCheckable)
                    entity_item.setCheckState(0, qtc.Qt.Checked if entity.name in entities_to_extract
                                              else qtc.Qt.Unchecked)
                    self.entities[entity.name] = [entity_item, entity]

        self._load_from_settings()

    def _load_from_settings(self):
        self.opt_cryxmlFmt.setCurrentText(self.scdv.settings.value('entity_extractor/opt_cryxmlFmt', 'xml').lower())
        self.opt_imgFmt.setCurrentText(self.scdv.settings.value('entity_extractor/opt_imgFmt', 'png').lower())
        self.opt_autoUnsplitTextures.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_autoUnsplitTextures', 'true')
        ))
        self.opt_autoConvertTextures.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_autoConvertTextures', 'true')
        ))
        self.opt_autoConvertSounds.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_autoConvertSounds', 'true')
        ))
        self.opt_autoConvertModels.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_autoConvertModels', 'true')
        ))
        self.opt_createSubFolder.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_createSubFolder', 'false')
        ))
        self.opt_genModelLog.setChecked(strtobool(
            self.scdv.settings.value('entity_extractor/opt_genModelLog', 'false')
        ))

    def _save_settings(self):
        self.scdv.settings.setValue('entity_extractor/opt_cryxmlFmt', self.opt_cryxmlFmt.currentText())
        self.scdv.settings.setValue('entity_extractor/opt_imgFmt', self.opt_imgFmt.currentText())
        self.scdv.settings.setValue('entity_extractor/opt_autoUnsplitTextures',
                                    self.opt_autoUnsplitTextures.isChecked())
        self.scdv.settings.setValue('entity_extractor/opt_autoConvertTextures',
                                    self.opt_autoConvertTextures.isChecked())
        self.scdv.settings.setValue('entity_extractor/opt_autoConvertSounds', self.opt_autoConvertSounds.isChecked())
        self.scdv.settings.setValue('entity_extractor/opt_autoConvertModels', self.opt_autoConvertModels.isChecked())
        self.scdv.settings.setValue('entity_extractor/opt_createSubFolder', self.opt_createSubFolder.isChecked())
        self.scdv.settings.setValue('entity_extractor/opt_genModelLog', self.opt_genModelLog.isChecked())

    @Slot(qtc.QPoint)
    def _show_ctx_menu(self, pos):
        self.ctx_menu.exec_(self.entityTree.mapToGlobal(pos))

    def _expand_all(self):
        for folder in self.tree_folders.values():
            folder.setExpanded(True)

    def _collapse_all(self):
        for folder in self.tree_folders.values():
            folder.setExpanded(False)

    def on_item_doubleclick(self, item):
        if item.childCount() == 0:
            item.setCheckState(0, qtc.Qt.Checked if item.checkState(0) == qtc.Qt.Unchecked else qtc.Qt.Unchecked)
        else:
            item.setExpanded(not item.isExpanded())

    @Slot(str)
    def on_filter_text_changed(self, filter_str):
        filter_str = filter_str.lower()
        parents = set()
        for item, _ in self.entities.values():
            if filter_str:
                if filter_str in item.text(0).lower():
                    parents.add(item.parent())
                    item.setHidden(False)
                else:
                    item.setHidden(True)
            else:
                item.setHidden(False)
        self._collapse_all()

        def _expand_tree(item):
            if item.parent() is not None:
                _expand_tree(item.parent())
            item.setExpanded(True)

        for parent in parents:
            if parent is not None:
                _expand_tree(parent)

    def _set_checked(self, state, all=False):
        for item, _ in self.entities.values():
            if not item.isHidden() or all:
                item.setCheckState(0, state)

    def select_all(self):
        self._set_checked(qtc.Qt.Checked)

    def deselect_all(self):
        self._set_checked(qtc.Qt.Unchecked, all=True)

    def handle_extract(self):
        self._save_settings()
        selected_entities = []
        for item, record in self.entities.values():
            if item.checkState(0) == qtc.Qt.Checked:
                selected_entities.append(record)

        if not selected_entities:
            return qtw.QMessageBox.warning(None, 'Entity Extractor', 'Select at least one entity to export')

        self.hide()
        edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Save To...')
        if edir:
            options = {
                'convert_cryxml_fmt': self.opt_cryxmlFmt.currentText().lower(),
                'convert_dds_fmt': self.opt_imgFmt.currentText().lower(),
                'auto_unsplit_textures': self.opt_autoUnsplitTextures.isChecked(),
                'auto_convert_textures': self.opt_autoConvertTextures.isChecked(),
                'auto_convert_sounds': self.opt_autoConvertSounds.isChecked(),
                'auto_convert_models': self.opt_autoConvertModels.isChecked(),
                'cgf_converter': get_cgf_converter(), 'tex_converter': image_converter.converter,
                'ww2ogg': WW2OGG, 'revorb': REVORB,
            }
            dlg = EntityExportLog(scdv=self.scdv, outdir=edir, entities=selected_entities,
                                  create_entity_dir=self.opt_createSubFolder.isChecked(),
                                  output_model_log=self.opt_genModelLog.isChecked(),
                                  export_options=options)
            dlg.show()
            dlg.extract_entities()
        else:
            return qtw.QMessageBox.warning(None, 'Entity Extractor',
                                           'You must select an export directory to extract')

        self.close()
        self.destroy()
