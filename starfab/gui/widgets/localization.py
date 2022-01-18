import io
import csv

from starfab.gui import qtc, qtg
from starfab.resources import RES_PATH
from starfab.gui.widgets.dock_widgets.common import StarFabStaticWidget


class LocalizationView(StarFabStaticWidget):
    __ui_file__ = str(RES_PATH / "ui" / "LocalizationView.ui")

    def __init__(self, starfab, proxy_model=None, *args, **kwargs):
        super().__init__(starfab, *args, **kwargs)

        self.debounce = qtc.QTimer()
        self.debounce.setInterval(500)
        self.debounce.setSingleShot(True)
        self.debounce.timeout.connect(self._update_search)

        self.starfab.sc_manager.localization_model.loaded.connect(
            self.handle_localization_loaded
        )
        self.starfab.sc_manager.localization_model.unloading.connect(
            self.handle_localization_unloaded
        )

        self.proxy_model = None
        self.table.setWordWrap(True)
        self.table.installEventFilter(self)
        # self.table.horizontalHeader().sectionResized.connect(self.table.resizeRowsToContents)

        self.search_bar.textChanged.connect(self.debounce.start)
        self.search_bar.setClearButtonEnabled(True)

    def _create_proxy_model(self):
        self.proxy_model = qtc.QSortFilterProxyModel(self)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseInsensitive)
        self.proxy_model.setFilterRole(qtc.Qt.UserRole)

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
            self.copy_selection()
            return True
        return super().eventFilter(source, event)

    def handle_localization_loaded(self):
        self._create_proxy_model()
        self.proxy_model.setSourceModel(self.starfab.sc_manager.localization_model)
        self.table.setModel(self.proxy_model)
        self.table.setColumnWidth(0, 300)
        for i in range(1, self.proxy_model.columnCount(qtc.QModelIndex())):
            self.table.setColumnWidth(i, 200)

    def handle_localization_unloaded(self):
        del self.proxy_model
        self._create_proxy_model()
        self.table.setModel(self.proxy_model)
