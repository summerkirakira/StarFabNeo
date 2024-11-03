import typing
from pathlib import Path

from starfab.gui import qtw, qtc
from starfab.log import getLogger

logger = getLogger(__name__)


class QListDialog(qtw.QDialog):
    def __init__(self, title, items: typing.List[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setMinimumSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~qtc.Qt.WindowType.WindowContextHelpButtonHint)
        self.setWindowTitle(self.tr(title))
        self.setSizeGripEnabled(True)

        items = items or []
        layout = qtw.QVBoxLayout()

        toolbar = qtw.QToolBar()
        add_btn = qtw.QPushButton(self.tr("+"))
        add_btn.clicked.connect(self._add_item)
        toolbar.addWidget(add_btn)

        rem_btn = qtw.QPushButton(self.tr("-"))
        rem_btn.clicked.connect(self._remove_item)
        toolbar.addWidget(rem_btn)
        layout.addWidget(toolbar)

        self.list_widget = qtw.QListWidget()

        if items:
            self.list_widget.addItems(items)
        self.list_widget.sortItems(qtc.Qt.SortOrder.AscendingOrder)
        layout.addWidget(self.list_widget)

        btns = qtw.QDialogButtonBox()
        btns.setStandardButtons(qtw.QDialogButtonBox.StandardButton.Ok | qtw.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.setLayout(layout)

    def _add_item(self):
        blender_path, _ = qtw.QFileDialog.getOpenFileName(
            self, "Select blender.exe", qtc.QDir.homePath(), "blender.exe (blender.exe)"
        )
        blender_path = Path(blender_path)
        if blender_path.is_file() and blender_path.stem.casefold() == 'blender':
            self.list_widget.addItem(blender_path.parent.as_posix())
        self.list_widget.sortItems(qtc.Qt.SortOrder.AscendingOrder)

    def _remove_item(self):
        selected_items = self.list_widget.selectedIndexes()
        for index in selected_items:
            self.list_widget.takeItem(index.row())
        self.list_widget.sortItems(qtc.Qt.SortOrder.AscendingOrder)

    def items(self):
        return [text for _ in range(self.list_widget.count()) if (text := self.list_widget.item(_).text().strip())]
