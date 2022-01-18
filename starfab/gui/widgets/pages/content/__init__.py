from pathlib import Path
from distutils.util import strtobool

from qtpy import uic
import qtawesome as qta

from starfab.gui import qtc, qtw, qtg
from starfab.log import getLogger
from starfab.resources import RES_PATH
from starfab.settings import get_cgf_converter, get_ww2ogg, get_revorb
from starfab.utils import image_converter
from starfab.hooks import GEOMETRY_PREVIEW_WIDGET
from starfab.plugins import plugin_manager

from .soc_selector import SOCSelector
from .entity_selector import EntitySelector
from .weapon_selector import WeaponSelector
from .prefab_selector import PrefabSelector
from .vehicle_selector import VehicleSelector
from .character_selector import CharacterSelector
from .export_log import BlueprintExportLog, ExtractionItem
from starfab.gui.widgets.export_utils import ExportOptionsWidget
from starfab.gui.widgets.dock_widgets.audio_widget import AudioTreeWidget

logger = getLogger(__name__)


class ContentView(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab
        uic.loadUi(
            str(RES_PATH / "ui" / "ContentView.ui"), self
        )  # Load the ui into self
        # self.starfab.sc_manager.datacore_model.loaded.connect(self.handle_datacore_opened)

        self.starfab.close.connect(self.close)

        self.toolButton_Job_MoveUp.setIcon(qta.icon("mdi.arrow-up-bold-box"))
        self.toolButton_Job_MoveDown.setIcon(qta.icon("mdi.arrow-down-bold-box"))
        self.toolButton_Job_Remove.setIcon(qta.icon("mdi.minus-box"))

        self.buttonBox_Content.accepted.connect(self.handle_extract)
        self.buttonBox_Content.button(qtw.QDialogButtonBox.Save).setText("Export")
        # self.buttonBox_Content.button(qtw.QDialogButtonBox.Open).setText("Add Job")
        # self.buttonBox_Content.button(qtw.QDialogButtonBox.Open).setVisible(False)

        self.toolBox = qtw.QToolBox(self.tab_Assets)
        self.toolBox.addItem(VehicleSelector(content_page=self), "Vehicles")
        self.toolBox.addItem(WeaponSelector(content_page=self), "Weapons")
        self.toolBox.addItem(CharacterSelector(content_page=self), "Character")
        self.toolBox.addItem(SOCSelector(content_page=self), "Object Containers")
        self.toolBox.addItem(PrefabSelector(content_page=self), "Prefabs")
        self.toolBox.addItem(EntitySelector(content_page=self), "Entities")
        self.tab_Assets.layout().addWidget(self.toolBox)

        self.export_options = ExportOptionsWidget(parent=self)
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
            options = {
                "cgf_converter_bin": get_cgf_converter(),
                "ww2ogg": get_ww2ogg(),
                "revorb": get_revorb(),
                "tex_converter": image_converter.converter,
                "tex_converter_bin": image_converter.converter_bin,
            }
            options.update(self.export_options.get_options())
            options["auto_convert_textures"] = (
                "ddstexture_converter" in options["converters"]
            )
            options["auto_convert_models"] = "cgf_converter" in options["converters"]

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
