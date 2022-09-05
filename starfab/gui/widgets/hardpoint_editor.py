from functools import partial
from pathlib import Path

from scdatatools.forge.dco import dco_from_datacore
from scdatatools.forge.dco.entities import Vehicle
from scdatatools.forge.dftypes import Record
from scdatatools.sc.blueprints.generators.datacore_entity import blueprint_from_datacore_entity
from starfab import get_starfab
from starfab.gui import qtw, qtc
from starfab.gui.widgets.pages.content.export_log import BlueprintExportLog, ExtractionItem


class HardpointEditor(qtw.QWidget):
    def __init__(self, export_options, parent=None):
        super().__init__(parent=parent)
        self.setSizePolicy(qtw.QSizePolicy(qtw.QSizePolicy.Preferred, qtw.QSizePolicy.Preferred))
        self.starfab = get_starfab()
        self.export_options = export_options
        layout = qtw.QFormLayout(self)
        self.vehicle = None
        self.blueprint = None
        self.hardpoint_options = {}

    def set_vehicle(self, vehicle: Record | Vehicle):
        self.clear()
        if isinstance(vehicle, Record):
            vehicle = dco_from_datacore(self.starfab.sc, vehicle)
        if not isinstance(vehicle, Vehicle):
            raise AttributeError(f'Invalid type {vehicle}')
        self.vehicle = vehicle
        self.blueprint = blueprint_from_datacore_entity(self.starfab.sc, vehicle.object)
        self.build_constrained_options()

    def clear(self):
        layout = self.layout()
        while layout.rowCount() > 0:
            layout.removeRow(0)

    def _handle_hp_changed(self, hp, value):
        self.blueprint.update_hardpoint(hp, self.hardpoint_options[hp][value].object)

    def _get_bp(self, sc, record, monitor):
        self.blueprint.monitor = monitor
        self.blueprint._process()
        return self.blueprint

    def _handle_export(self):
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
                items=[ExtractionItem(self.vehicle.name, self.vehicle.object, self._get_bp)],
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

    def build_constrained_options(self):
        layout: qtw.QFormLayout = self.layout()
        self.hardpoint_options = {
            hp_name: {} for hp_name in self.vehicle.editable_hardpoints.keys()
        }
        for hp_name, hp in self.vehicle.editable_hardpoints.items():
            hp_options = set()
            if 'ItemPort' not in hp:
                continue
            for size in range(int(hp['ItemPort']['@minsize']), int(hp['ItemPort']['@maxsize']) + 1):
                types = hp['ItemPort']['Types']['Type']
                if isinstance(types, dict):
                    types = [types]
                for ac_type in types:
                    hp_options.update(self.starfab.sc.attachable_component_manager.filter(
                        size=size, type=ac_type['@type'], sub_types=ac_type.get('@subtypes', '').split(',')
                    ))
            cb = qtw.QComboBox()
            for opt in hp_options:
                ac_params = opt.components['SAttachableComponentParams']
                disp_name = self.starfab.sc.gettext(ac_params.display_name)
                cb.addItem(disp_name)
                cb.setItemData(cb.count(), self.starfab.sc.gettext(ac_params.description), qtc.Qt.ToolTipRole)
                self.hardpoint_options[hp_name][disp_name] = opt
            cb.currentTextChanged.connect(partial(self._handle_hp_changed, hp_name))
            layout.addRow(hp_name, cb)

        export_btn = qtw.QPushButton("Export")
        export_btn.clicked.connect(self._handle_export)
        layout.addWidget(export_btn)
