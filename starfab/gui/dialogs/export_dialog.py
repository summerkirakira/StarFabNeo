import os
import glob
import shutil
import typing
from pathlib import Path
from functools import partial

from qtpy import uic
from qtpy.QtCore import Signal, Slot
import qtawesome as qta
import qtvscodestyle as qtvsc

from scdatatools.utils import parse_bool

from starfab.log import getLogger
from starfab.gui import qtg, qtw, qtc
from starfab.settings import settings
from starfab.models.common import ExportRunner
from starfab.gui.widgets.export_utils import ExportOptionsWidget
from starfab.models.p4k import P4KItem

logger = getLogger(__name__)


class P4KExportDialog(qtw.QDialog):
    def __init__(self, p4k_items: typing.List[P4KItem], save_to=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowFlags(self.windowFlags() & ~qtc.Qt.WindowContextHelpButtonHint)
        self.setWindowTitle(self.tr("Export"))
        self.setFixedWidth(400)

        layout = qtw.QVBoxLayout()
        self.export_options = ExportOptionsWidget(
            exclude=['create_sub_folder', 'gen_model_log']
        )
        layout.addWidget(self.export_options)

        btns = qtw.QDialogButtonBox()
        btns.addButton(
            qtw.QPushButton(self.tr("Cancel")), qtw.QDialogButtonBox.RejectRole
        )
        btns.addButton(
            qtw.QPushButton(self.tr("Export")), qtw.QDialogButtonBox.AcceptRole
        )
        btns.accepted.connect(self.export)
        btns.rejected.connect(self.close)
        layout.addWidget(btns)
        self.setLayout(layout)

        self.save_to = save_to
        self.p4k_items = p4k_items

    @qtc.Slot()
    def export(self):
        prev_dir = settings.value("exportDirectory")

        title = "Save to..." if self.save_to else "Extract to..."
        edir = qtw.QFileDialog.getExistingDirectory(self, title, dir=prev_dir)
        if edir:
            options = self.export_options.get_options()
            export_runner = ExportRunner(
                p4k_files=[_.info for _ in self.p4k_items],
                outdir=edir,
                save_to=self.save_to,
                export_options=options,
            )
            qtc.QThreadPool.globalInstance().start(export_runner)
            self.close()
        else:
            return qtw.QMessageBox.warning(
                self, title, "You must select an export directory to extract"
            )
