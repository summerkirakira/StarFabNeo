import copy

from starfab.gui import qtc


class LocalizationModel(qtc.QAbstractTableModel):
    loaded = qtc.Signal()
    unloading = qtc.Signal()
    cancel_loading = qtc.Signal()

    def __init__(self, sc_manager=None):
        super().__init__(parent=sc_manager)

        self._sc_manager = sc_manager
        self.columns = ["Name"]
        self.localization = None
        self.languages = None
        self.names = []

        self._sc_manager.p4k_model.loaded.connect(self._on_p4k_loaded)
        self._sc_manager.p4k_model.unloading.connect(
            self._on_p4k_unloading,  # qtc.Qt.BlockingQueuedConnection
        )

    @qtc.Slot()
    def _on_p4k_loaded(self):
        self.localization = self._sc_manager.sc.localization
        self.languages = list(sorted(self.localization.languages))
        self.languages.remove(self.localization.default_language)
        self.languages.insert(0, self.localization.default_language)
        self.translations = copy.copy(self.localization.translations)

        self.beginInsertColumns(qtc.QModelIndex(), 0, len(self.columns))
        self.columns = ["Name"] + self.languages
        self.endInsertColumns()

        self.beginInsertRows(qtc.QModelIndex(), 0, len(self.names))
        self.names = list(self.translations["english"].keys())
        self.endInsertColumns()
        self.loaded.emit()

    @qtc.Slot()
    def _on_p4k_unloading(self):
        self.unloading.emit()
        self.beginRemoveRows(qtc.QModelIndex(), 0, len(self.names))
        self.names = []
        self.endRemoveRows()

        self.beginRemoveColumns(qtc.QModelIndex(), 1, len(self.columns))
        self.columns = ["Name"]
        self.endRemoveColumns()

        self.localization = None
        self.languages = None

    def columnCount(self, parent):
        return len(self.columns)

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.names)

    def headerData(self, section, orientation, role=None):
        if role == qtc.Qt.DisplayRole and orientation == qtc.Qt.Horizontal:
            try:
                return self.columns[section]
            except IndexError:
                pass
        return None

    def data(self, index, role=None):
        if index.isValid() and index.row() <= len(self.names):
            name = self.names[index.row()]
            if role == qtc.Qt.DisplayRole or role == qtc.Qt.ToolTipRole:
                if index.column() == 0:
                    return name
                return self.translations[self.columns[index.column()]].get(name, "")
            elif index.column() == 0 and role == qtc.Qt.UserRole:
                # User role will be the proxy filtering. send it back all the data so it will search all columns
                return f"{self.names[index.row()]} " + " ".join(
                    self.translations[lang].get(name, "") for lang in self.languages
                )
        return None
