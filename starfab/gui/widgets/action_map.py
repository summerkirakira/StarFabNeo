import csv
import io

from scdatatools.sc.config import ACTION_MAP_FIELD_NAMES
from starfab.gui import qtc, qtg, qtw
from starfab.gui.widgets.dock_widgets.common import StarFabStaticWidget
from starfab.resources import RES_PATH


class ActionItem(qtg.QStandardItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(False)


class ActionMapView(StarFabStaticWidget):
    __ui_file__ = str(RES_PATH / "ui" / "ActionMapView.ui")

    def __init__(self, starfab, proxy_model=None, *args, **kwargs):
        super().__init__(starfab, *args, **kwargs)

        self.debounce = qtc.QTimer()
        self.debounce.setInterval(500)
        self.debounce.setSingleShot(True)
        self.debounce.timeout.connect(self._update_search)

        self.starfab.sc_manager.p4k_model.loaded.connect(self.handle_sc_opened)

        self.tree_model = None
        self.proxy_model = qtc.QSortFilterProxyModel(self)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.tree.installEventFilter(self)

        self.search_bar.textChanged.connect(self.debounce.start)
        self.search_bar.setClearButtonEnabled(True)
        self.exportButton.clicked.connect(self.export)

        # TODO: filter will require some tweaking to show parents before search works
        # self.search_bar.hide()

    def _update_search(self):
        self.proxy_model.setFilterWildcard(self.search_bar.text())

    def copy_selection(self):
        selections = self.table.selectedIndexes()
        if len(selections) == 1:
            qtg.QGuiApplication.clipboard().setText(selections[0].data())
        else:
            rows = sorted(index.row() for index in selections)
            columns = sorted(index.column() for index in selections)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[""] * colcount for _ in range(rowcount)]
            for index in selections:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream).writerows(table)
            qtg.QGuiApplication.clipboard().setText(stream.getvalue())

    def eventFilter(self, source, event):
        if event.type() == qtc.QEvent.KeyPress and event.matches(qtg.QKeySequence.Copy):
            # self.copy_selection()
            return True
        return super().eventFilter(source, event)

    def _fill_tree(self):
        self.tree_model.setHorizontalHeaderLabels(ACTION_MAP_FIELD_NAMES + ["filter"])
        am = self.starfab.sc.default_profile.actionmap()
        root = self.tree_model.invisibleRootItem()
        # empty_action_item = ActionItem("")
        for ui_category, action_category in am.items():
            ui_category_item = ActionItem(ui_category)
            root.appendRow([ui_category_item])
            for category, actions in action_category.items():
                category_item = ActionItem(category)
                ui_category_item.appendRow([category_item])
                for label, action in actions.items():
                    row = [ActionItem(""), ActionItem(label)]
                    row[1].setToolTip(label)
                    for _ in ACTION_MAP_FIELD_NAMES[2:]:
                        txt = str(action.get(_, ""))
                        row.append(ActionItem(txt))
                        row[-1].setToolTip(txt)
                    row.append(
                        ActionItem(
                            "".join(
                                [category, label] + [str(_) for _ in action.values()]
                            )
                        )
                    )
                    category_item.appendRow(row)

    def export(self):
        path, _ = qtw.QFileDialog.getSaveFileName(self, "Export Action Map", '', "*.csv")
        if path:
            with open(path, 'w', newline='') as out:
                self.starfab.sc.default_profile.dump_actionmap_csv(out)

    def handle_sc_opened(self):
        if self.starfab.sc is not None and self.starfab.sc.is_loaded("p4k"):
            self.tree_model = qtg.QStandardItemModel(self)
            self._fill_tree()
            self.proxy_model.setSourceModel(self.tree_model)
            self.proxy_model.setFilterKeyColumn(len(ACTION_MAP_FIELD_NAMES))
            self.tree.setModel(self.proxy_model)
            self.tree.hideColumn(len(ACTION_MAP_FIELD_NAMES))
            self.tree.setWordWrap(True)
            self.tree.setAlternatingRowColors(True)
            self.tree.setColumnWidth(0, 250)
            self.tree.setColumnWidth(1, 250)
            self.tree.setSortingEnabled(True)
            self.tree.sortByColumn(0, qtc.Qt.AscendingOrder)
            self.tree.expandAll()
