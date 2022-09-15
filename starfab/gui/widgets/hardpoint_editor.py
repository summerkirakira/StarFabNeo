from functools import partial
from pathlib import Path

from scdatatools.forge.dco import dco_from_datacore
from scdatatools.forge.dco.entities import Vehicle
from scdatatools.forge.dftypes import Record
from scdatatools.sc.blueprints.generators.datacore_entity import blueprint_from_datacore_entity
from starfab import get_starfab
from starfab.gui import qtw, qtc
from starfab.gui.widgets.pages.content.export_log import BlueprintExportLog, ExtractionItem

OPTION_EMPTY_LABEL = '--------'


class HardpointEditor(qtw.QWidget):
    def __init__(self, export_options, parent=None):
        super().__init__(parent=parent)
        self.setSizePolicy(qtw.QSizePolicy(qtw.QSizePolicy.Expanding, qtw.QSizePolicy.Expanding))
        self.starfab = get_starfab()
        self.export_options = export_options
        self.setFixedWidth(500)

        layout = qtw.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = qtw.QScrollArea()
        self.form_widget = qtw.QWidget()
        self.form_widget.setFixedWidth(480)
        self.form_layout = qtw.QFormLayout(self.form_widget)
        self.scroll.setVerticalScrollBarPolicy(qtc.Qt.ScrollBarAsNeeded)
        self.scroll.setFixedWidth(500)
        self.scroll.setHorizontalScrollBarPolicy(qtc.Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.form_widget)
        layout.addWidget(self.scroll)

        self.fun_mode = qtw.QCheckBox("Creative Mode")
        self.fun_mode.stateChanged.connect(self._toggle_fun_mode)
        layout.addWidget(self.fun_mode)

        self.export_btn = qtw.QPushButton("Export")
        self.export_btn.clicked.connect(self._handle_export)
        layout.addWidget(self.export_btn)

        self.vehicle = None
        self.blueprint = None
        self.hardpoint_options = {}
        self.toggle_controls()

    def _toggle_fun_mode(self, state):
        self.build_options()

    def toggle_controls(self):
        vis = bool(self.hardpoint_options)
        self.fun_mode.setVisible(vis)
        self.export_btn.setVisible(vis)

    def set_vehicle(self, vehicle: Record | Vehicle):
        self.clear()
        if isinstance(vehicle, Record):
            vehicle = dco_from_datacore(self.starfab.sc, vehicle)
        if not isinstance(vehicle, Vehicle):
            raise AttributeError(f'Invalid type {vehicle}')
        self.vehicle = vehicle
        self.blueprint = blueprint_from_datacore_entity(self.starfab.sc, vehicle.object)
        self.build_options()

    def clear(self):
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)

    def _handle_hp_changed(self, hp, value):
        obj = None if value == OPTION_EMPTY_LABEL else self.hardpoint_options[hp][value].object
        self.blueprint.update_hardpoint(hp, obj)

    def _get_bp(self, sc, record, monitor):
        self.blueprint.monitor = monitor
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

    def _build_combobox(self, hp_name, hp_options):
        hp_default = self.vehicle.default_loadout.get(hp_name, '')
        default_text = OPTION_EMPTY_LABEL
        cb = qtw.QComboBox()
        cb.addItem(OPTION_EMPTY_LABEL)
        for opt in sorted(hp_options, key=lambda o: o.disp_name, reverse=True):
            cb.addItem(opt.disp_name)
            cb.setItemData(cb.count(), opt.description, qtc.Qt.ToolTipRole)
            self.hardpoint_options[hp_name][opt.disp_name] = opt
            if opt.name == hp_default:
                default_text = opt.disp_name
        cb.setCurrentText(default_text)
        cb.currentTextChanged.connect(partial(self._handle_hp_changed, hp_name))
        return cb

    def _get_fun_options(self, hp_name, hp):
        hp_options = set()
        for size in range(1, 13):
            types = hp['ItemPort']['Types']['Type']
            if isinstance(types, dict):
                types = [types]
            for ac_type in types:
                hp_options |= self.starfab.sc.attachable_component_manager.filter(
                    size=size, type=ac_type['@type'], sub_types=ac_type.get('@subtypes', '').split(',')
                )
        return hp_options

    def _get_constrained_options(self, hp_name, hp):
        hp_options = set()
        for size in range(int(hp['ItemPort']['@minsize']), int(hp['ItemPort']['@maxsize']) + 1):
            try:
                types = hp['ItemPort']['Types']['Type']
                if isinstance(types, dict):
                    types = [types]
                for ac_type in types:
                    hp_options |= self.starfab.sc.attachable_component_manager.filter(
                        size=size, type=ac_type['@type'], sub_types=ac_type.get('@subtypes', '').split(',')
                    )
            except KeyError:
                pass
        return hp_options

    def build_options(self):
        self.clear()

        self.hardpoint_options = {
            hp_name: {} for hp_name in self.vehicle.editable_hardpoints.keys()
        }

        for hp_name, hp in self.vehicle.editable_hardpoints.items():
            if 'ItemPort' not in hp:
                continue
            if self.fun_mode.isChecked():
                filtered_options = self._get_fun_options(hp_name, hp)
            else:
                filtered_options = self._get_constrained_options(hp_name, hp)
            hp_options = []
            for o in filtered_options:
                ac_params = o.components['SAttachableComponentParams']
                o.disp_name = self.starfab.sc.gettext(ac_params.display_name)
                o.description = self.starfab.sc.gettext(ac_params.description)
                hp_options.append(o)
            self.form_layout.addRow(hp_name, self._build_combobox(hp_name, hp_options))
        self.toggle_controls()

    # def build_constrained_options(self):
    #     layout: qtw.QFormLayout = self.layout()
    #     self.hardpoint_options = {
    #         hp_name: {} for hp_name in self.vehicle.editable_hardpoints.keys()
    #     }
    #     for hp_name, hp in self.vehicle.editable_hardpoints.items():
    #         hp_options = set()
    #         if 'ItemPort' not in hp:
    #             continue
    #         for size in range(int(hp['ItemPort']['@minsize']), int(hp['ItemPort']['@maxsize']) + 1):
    #             types = hp['ItemPort']['Types']['Type']
    #             if isinstance(types, dict):
    #                 types = [types]
    #             for ac_type in types:
    #                 hp_options.update(self.starfab.sc.attachable_component_manager.filter(
    #                     size=size, type=ac_type['@type'], sub_types=ac_type.get('@subtypes', '').split(',')
    #                 ))
    #         cb = qtw.QComboBox()
    #         for opt in hp_options:
    #             ac_params = opt.components['SAttachableComponentParams']
    #             disp_name = self.starfab.sc.gettext(ac_params.display_name)
    #             cb.addItem(disp_name)
    #             cb.setItemData(cb.count(), self.starfab.sc.gettext(ac_params.description), qtc.Qt.ToolTipRole)
    #             self.hardpoint_options[hp_name][disp_name] = opt
    #         cb.currentTextChanged.connect(partial(self._handle_hp_changed, hp_name))
    #         self.form_layout.addRow(hp_name, cb)
    #
    #     export_btn = qtw.QPushButton("Export")
    #     export_btn.clicked.connect(self._handle_export)
    #     self.form_layout.addWidget(export_btn)
