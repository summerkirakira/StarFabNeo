from qtpy import uic

from starfab.gui import qtw
from starfab.gui.dialogs.lists_dialog import ListsDialog
from starfab.resources import RES_PATH
from starfab.utils import open_color_dialog


class PreviewOptions(qtw.QWidget):
    def __init__(self, starfab):
        super().__init__(parent=None)
        self.starfab = starfab

        uic.loadUi(str(RES_PATH / "ui" / "PreviewOptions.ui"), self)

        self.btn_color_pick_pc.clicked.connect(self.handle_color_picker)
        self.btn_color_pick_cc.clicked.connect(self.handle_color_picker)

        self.btn_root_excluded_nodes.clicked.connect(self.handle_filter_list_1)
        self.btn_root_node_del.clicked.connect(self.handle_filter_list_2)
        self.btn_root_mtl_del.clicked.connect(self.handle_filter_list_3)
        self.btn_sub_node_del.clicked.connect(self.handle_filter_list_4)
        self.btn_sub_mtl_del.clicked.connect(self.handle_filter_list_5)

    def handle_color_picker(self):
        color = open_color_dialog()
        if color is not None:
            self.sender().setStyleSheet(f'background-color: {color};')

    def handle_filter_list_1(self):
        name = "Root Excluded Nodes"
        dlg = ListsDialog(name, self.starfab.preview.root_excluded_nodes)
        dlg.exec_()

    def handle_filter_list_2(self):
        name = "Root Node Deletes"
        dlg = ListsDialog(name, self.starfab.preview.root_node_del)
        dlg.exec_()

    def handle_filter_list_3(self):
        name = "Root Material Deletes"
        dlg = ListsDialog(name, self.starfab.preview.root_mtl_del)
        dlg.exec_()

    def handle_filter_list_4(self):
        name = "Sub Node Deletes"
        dlg = ListsDialog(name, self.starfab.preview.sub_node_del)
        dlg.exec_()

    def handle_filter_list_5(self):
        name = "Sub Material Deletes"
        dlg = ListsDialog(name, self.starfab.preview.sub_mtl_del)
        dlg.exec_()
