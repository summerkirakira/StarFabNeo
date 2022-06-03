from pathlib import Path

import qtawesome as qta
from qtpy import uic

from starfab.gui import qtw
from starfab.gui.widgets.dock_widgets.audio_widget import AudioTreeWidget
from starfab.gui.widgets.export_utils import ExportOptionsWidget
from starfab.hooks import GEOMETRY_PREVIEW_WIDGET
from starfab.log import getLogger
from starfab.plugins import plugin_manager
from starfab.resources import RES_PATH
from .character_selector import CharacterSelector
from .entity_selector import EntitySelector
from .export_log import BlueprintExportLog, ExtractionItem
from .prefab_selector import PrefabSelector
from .soc_selector import SOCSelector
from .vehicle_selector import VehicleSelector
from .weapon_selector import WeaponSelector

logger = getLogger(__name__)


class ContentView(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        uic.loadUi(
            str(RES_PATH / "ui" / "ContentView.ui"), self
        )  # Load the ui into self

        self.starfab.close.connect(self.close)

        self.toolButton_Job_MoveUp.setIcon(qta.icon("mdi.arrow-up-bold-box"))
        self.toolButton_Job_MoveDown.setIcon(qta.icon("mdi.arrow-down-bold-box"))
        self.toolButton_Job_Remove.setIcon(qta.icon("mdi.minus-box"))

        self.buttonBox_Content.accepted.connect(self.handle_extract)
        self.buttonBox_Content.button(qtw.QDialogButtonBox.Save).setText("Export")

        self.toolBox = qtw.QToolBox(self.tab_Assets)
        self.toolBox.addItem(VehicleSelector(content_page=self), "Vehicles")
        self.toolBox.addItem(WeaponSelector(content_page=self), "Weapons")
        self.toolBox.addItem(CharacterSelector(content_page=self), "Character")
        self.toolBox.addItem(SOCSelector(content_page=self), "Object Containers")
        self.toolBox.addItem(PrefabSelector(content_page=self), "Prefabs")
        self.toolBox.addItem(EntitySelector(content_page=self), "Entities")
        self.tab_Assets.layout().addWidget(self.toolBox)

        clear_selections_btn = qtw.QPushButton('Clear Selections')
        clear_selections_btn.clicked.connect(self.clear_assets_selections)
        self.tab_Assets.layout().addWidget(clear_selections_btn)

        self.export_options = ExportOptionsWidget(exclude=['extract_model_assets'], parent=self)
        self.options_layout.insertWidget(0, self.export_options)

        self.audio_tree = AudioTreeWidget(starfab=self.starfab, parent=self)
        self.tab_Audio.layout().addWidget(self.audio_tree)

        # TODO: temporarily hide things that arent fleshed out yet
        self.content_left_tab_widget.setTabVisible(
            self.content_left_tab_widget.indexOf(self.tab_Images), False
        )
        self.content_right_tab_widget.setTabVisible(
            self.content_right_tab_widget.indexOf(self.tab_Jobs), False
        )
        self.groupBox_Content_Local_Files.hide()

        prev_handlers = plugin_manager.hooks(GEOMETRY_PREVIEW_WIDGET)
        if prev_handlers:
            self.preview = prev_handlers[0][1]["handler"](
                allow_popout=False, parent=self
            )
            self.preview_widget_layout.addWidget(self.preview)
        else:
            self.preview = None
            self.splitter.setSizes((1, 0))

    def clear_assets_selections(self):
        for i in range(self.toolBox.count()):
            widget: EntitySelector = self.toolBox.widget(i)
            widget.deselect_all()

    def closeEvent(self, event):
        if self.preview is not None:
            self.preview.deleteLater()
        return super().closeEvent(event)

    def preview_chunkfile(self, chunkfile_or_tabs, name=None):
        if self.preview is not None:
            if isinstance(chunkfile_or_tabs, dict):
                self.preview.set_tabs(chunkfile_or_tabs)
            else:
                self.preview.clear()
                self.preview.load_mesh(chunkfile_or_tabs, name=name)

    def handle_extract(self):
        selector = self.toolBox.currentWidget()
        selected_items = selector.checked_items()

        if not selected_items:
            return qtw.QMessageBox.warning(
                None, "Content Extractor", "Select at least one item to export"
            )

        if self.starfab.settings.value("exportDirectory") is not None or "":
            edir = Path(self.starfab.settings.value("exportDirectory")).as_posix()
        else:
            edir = Path("~").expanduser().as_posix()
        edir = qtw.QFileDialog.getExistingDirectory(self.starfab, "Export To...", edir)

        if Path(edir).is_dir():
            options = self.export_options.get_options()

            dlg = BlueprintExportLog(
                starfab=self.starfab,
                outdir=edir,
                items=selected_items,
                create_entity_dir=options.pop("create_sub_folder"),
                output_model_log=options.pop("gen_model_log"),
                export_options=options,
            )
            dlg.show()
            dlg.extract_entities()
        else:
            return qtw.QMessageBox.warning(
                None,
                "Entity Extractor",
                "You must select an export directory to extract",
            )
