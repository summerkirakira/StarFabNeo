import shutil
from pathlib import Path
from functools import partial
from datetime import datetime

from qtpy import uic
from qtpy.QtCore import Slot

from scdv import CONTRIB_DIR
from scdv.ui import qtg, qtw, qtc
from scdv.resources import RES_PATH
from scdv.utils import show_file_in_filemanager
from scdv.ui.widgets.dock_widgets.audio import WW2OGG, REVORB

from scdatatools.sc.utils import extract_ship, CGF_CONVERTER_MODEL_EXTS

SHIP_ENTITES_PATH = 'libs/foundry/records/entities/spaceships'
CGF_CONVERTER = shutil.which('cgf-converter.exe')
if CGF_CONVERTER is None and (CONTRIB_DIR / 'cgf-converter.exe').is_file():
    CGF_CONVERTER = Path(CONTRIB_DIR / 'cgf-converter.exe')


class ShipEntityExportLog(qtw.QDialog):
    def __init__(self, scdv, outdir, ships, create_ship_dir=True, output_model_log=False, export_options=None):
        super().__init__(parent=scdv)
        self.setMinimumSize(1024, 800)
        self.scdv = scdv
        self.export_options = export_options or {}
        self.create_ship_dir = create_ship_dir
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

        self.ships = ships
        self.outdir = Path(outdir)

    def closeEvent(self, event) -> None:
        if self.closebtn.isEnabled():
            event.accept()
        else:
            event.ignore()

    def _output_monitor(self, msg, ship, console, default_fmt, log_file, model_log_file, overview_console):
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
            overview_console.append(f'{ship}: {msg}')
        log_file.write(f'{msg}\n')
        if (model_log_file and msg.startswith('zstd |') and
                any(msg.lower().endswith(_) for _ in CGF_CONVERTER_MODEL_EXTS)):
            model_log_file.write(msg.split(' | ')[-1])
        qtg.QGuiApplication.processEvents()

    def extract_ships(self) -> None:
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
        overview_console.append('-'*80)

        start = datetime.now()
        for i, ship in enumerate(self.ships):
            model_log = ''
            try:
                tab = qtw.QWidget()
                layout = qtw.QVBoxLayout()
                console = qtw.QTextEdit(tab)
                console.setReadOnly(True)
                layout.addWidget(console)
                tab.setLayout(layout)
                self.output_tabs.addTab(tab, ship.name)
                self.output_tabs.setCurrentWidget(tab)

                self.setWindowTitle(f'Extracting Ship {i+1}/{len(self.ships)}: {ship.name} ({ship.id})')
                ship_output_dir = self.outdir / ship.name if self.create_ship_dir else self.outdir
                logfile = ship_output_dir / f'{datetime.now().strftime("%Y_%m_%d-%H_%M_%S")}_{ship.name}.extraction.log'
                logfile.parent.mkdir(parents=True, exist_ok=True)

                if self.output_model_log:
                    model_log = (ship_output_dir / f'{datetime.now().strftime("%Y_%m_%d-%H_%M_%S")}_{ship.name}'
                                                   f'.extracted_models.log').open('w')

                with logfile.open('w') as log:
                    extract_ship(self.scdv.sc, ship.id, outdir=ship_output_dir,
                                 monitor=partial(self._output_monitor, console=console, ship=ship.name,
                                                 default_fmt=default_fmt, log_file=log, model_log_file=model_log,
                                                 overview_console=overview_console),
                                 **self.export_options
                                 )
            except Exception as e:
                print(f'ERROR EXTRACTING SHIP {ship}: {e}')
            finally:
                if model_log:
                    model_log.close()

        overview_console.setCurrentCharFormat(default_fmt)
        overview_console.append('-'*80)
        overview_console.append(f'\n\nFinished exporting {len(self.ships)} ships in {datetime.now() - start}')
        overview_console.append(f'Output directory: {self.outdir}')
        self.output_tabs.setCurrentWidget(overview_tab)
        show_file_in_filemanager(Path(self.outdir))
        self.closebtn.setEnabled(True)


class ShipEntityExporterDialog(qtw.QDialog):
    def __init__(self, scdv):
        super().__init__(parent=None)
        self.scdv = scdv
        uic.loadUi(str(RES_PATH / 'ui' / 'ShipEntityExportDialog.ui'), self)  # Load the ui into self

        self.buttonBox.accepted.connect(self.handle_extract)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.button(qtw.QDialogButtonBox.Save).setText("Export")
        self.deselectAllButton.clicked.connect(self.deselect_all)
        self.selectAllButton.clicked.connect(self.select_all)

        self.listFilter.textChanged.connect(self.on_filter_text_changed)
        self.listWidget.itemDoubleClicked.connect(self.on_item_doubleclick)

        if self.scdv.sc is not None:
            self.ships = {s.name: s for s in self.scdv.sc.datacore.search_filename(f'{SHIP_ENTITES_PATH}/*')}
            for ship in sorted(self.ships.keys()):
                ship_item = qtw.QListWidgetItem(ship)
                ship_item.setFlags(ship_item.flags() | qtc.Qt.ItemIsUserCheckable)
                ship_item.setCheckState(qtc.Qt.Unchecked)
                self.listWidget.addItem(ship_item)

    def on_item_doubleclick(self, item):
        item.setCheckState(qtc.Qt.Checked if item.checkState() == qtc.Qt.Unchecked else qtc.Qt.Unchecked)

    @Slot(str)
    def on_filter_text_changed(self, filter_str):
        filter_str = filter_str.lower()
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            item.setHidden(filter_str not in item.text().lower() if filter_str else False)

    def _set_checked(self, state, all=False):
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            if not item.isHidden() or all:
                item.setCheckState(state)

    def select_all(self):
        self._set_checked(qtc.Qt.Checked)

    def deselect_all(self):
        self._set_checked(qtc.Qt.Unchecked, all=True)

    def handle_extract(self):
        selected_ships = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == qtc.Qt.Checked:
                selected_ships.append(self.ships[item.text()])

        if not selected_ships:
            return qtw.QMessageBox.warning(self, title='Ship Extractor', text='Select at least one ship to export')

        self.hide()
        edir = qtw.QFileDialog.getExistingDirectory(self.scdv, 'Save To...')
        if edir:
            options = {
                'auto_unsplit_textures': self.opt_autoUnsplitTextures.isChecked(),
                'auto_convert_textures': self.opt_autoConvertTextures.isChecked(),
                'auto_convert_sounds': self.opt_autoConvertSounds.isChecked(),
                'auto_convert_models': self.opt_autoConvertModels.isChecked(),
                'ww2ogg': WW2OGG, 'revorb': REVORB, 'cgf_converter': CGF_CONVERTER
            }
            dlg = ShipEntityExportLog(scdv=self.scdv, outdir=edir, ships=selected_ships,
                                      create_ship_dir=self.opt_createSubFolder.isChecked(),
                                      output_model_log=self.opt_genModelLog.isChecked(),
                                      export_options=options)
            dlg.show()
            dlg.extract_ships()
        else:
            return qtw.QMessageBox.warning(self, title='Ship Extractor',
                                           text='You must select an export directory to extract')

        self.close()
        self.destroy()
