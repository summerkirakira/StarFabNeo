from qtpy import QtGui
from qtpy.QtWidgets import QDialog, QListWidget, QLineEdit, QMessageBox, QVBoxLayout, QInputDialog, QPushButton, \
    QHBoxLayout


class ListsDialog(QDialog):
    def __init__(self, name, dict_list=None):
        super(ListsDialog, self).__init__()

        self.name = name
        self.list = QListWidget()

        if dict_list is not None:
            self.list.addItems(dict_list)
            self.list.setCurrentRow(0)

        vbox = QVBoxLayout()

        for text, slot in (("Add", self.add),

                           ("Edit", self.edit),
                           ("Remove", self.remove),
                           ("Sort", self.sort),
                           ("Close", self.close)):
            button = QPushButton(text)

            vbox.addWidget(button)
            button.clicked.connect(slot)

        hbox = QHBoxLayout()
        hbox.addWidget(self.list)
        hbox.addLayout(vbox)
        self.setLayout(hbox)
        self.setWindowTitle("Edit {0} List".format(self.name))

        self.setWindowIcon(QtGui.QIcon("icon.png"))

    def add(self):
        row = self.list.currentRow()
        title = "Add {0}".format(self.name)
        string, ok = QInputDialog.getText(self, title, title)
        if ok and string is not None:
            self.list.insertItem(row, string)

    def edit(self):
        row = self.list.currentRow()
        item = self.list.item(row)
        if item is not None:
            title = "Edit {0}".format(self.name)
            string, ok = QInputDialog.getText(self, title, title,
                                              QLineEdit.Normal, item.text())
            if ok and string is not None:
                item.setText(string)

    def remove(self):
        row = self.list.currentRow()
        item = self.list.item(row)
        if item is None:
            return
        reply = QMessageBox.question(self, "Remove {0}".format(
            self.name), "Remove {0} `{1}'?".format(
            self.name, str(item.text())),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            item = self.list.takeItem(row)
            del item

    def sort(self):
        self.list.sortItems()

    def close(self):
        self.accept()
