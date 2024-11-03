import io
from pathlib import Path

from starfab.gui import qtc, qtw, qtg
from starfab.gui.utils import icon_for_path
from starfab.gui.widgets.dock_widgets.common import StarFabSearchableTreeDockWidget


class SCFileSystemProxyModel(qtc.QSortFilterProxyModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.archive_sources = []

    def filterAcceptsRow(self, source_row, source_parent):
        if source_parent == self.sourceModel().index(self.sourceModel().rootPath()):
            return super().filterAcceptsRow(source_row, source_parent)
        return True


class FileSystemWrapper:
    def __init__(self, path):
        self.path = path
        self.name = path.name

    @property
    def info(self):
        return self.path

    @property
    def suffix(self):
        return self.path.suffix

    def contents(self):
        try:
            with self.path.open("rb") as f:
                c = f.read()
        except Exception as e:
            c = f"Failed to read {self.name}: {e}".encode("utf-8")
        return io.BytesIO(c)


class FileViewDock(StarFabSearchableTreeDockWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(self.tr("Local Files"))
        self.starfab.sc_manager.opened.connect(self.handle_file_opened)

        self.sc_tree_model = qtw.QFileSystemModel()
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.handle_file_opened()

    def _on_doubleclick(self, index):
        index = self.proxy_model.mapToSource(index)
        item = FileSystemWrapper(Path(self.sc_tree_model.filePath(index)))
        if item is not None:
            if ".dds" in item.path.name:
                basename = item.path.name.split(".dds")[0]
                items = [
                    FileSystemWrapper(_)
                    for _ in item.path.parent.glob(f"{basename}.dds*")
                ]
                self._handle_item_action(
                    {i.path.as_posix(): i for i in items}, self.sc_tree_model, index
                )
            elif item.path.suffix.lower() == ".p4k":
                self.starfab.show_p4k_view()
            else:
                self._handle_item_action(item, self.sc_tree_model, index)

    def handle_file_opened(self):
        if self.starfab.sc_manager.sc is not None:
            self.sc_tree_model.setRootPath(str(self.starfab.sc_manager.sc.game_folder))
            self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)
            self.sc_tree.setRootIndex(
                self.proxy_model.mapFromSource(
                    self.sc_tree_model.index(
                        str(self.starfab.sc_manager.sc.game_folder)
                    )
                )
            )
            header = self.sc_tree.header()
            header.setSectionResizeMode(qtw.QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, qtw.QHeaderView.ResizeMode.Stretch)
