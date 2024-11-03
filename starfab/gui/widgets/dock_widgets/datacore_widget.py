import operator
import os
import shutil
import time
import typing
from functools import partial
from pathlib import Path

from scdatatools.forge.dftypes import StructureInstance
from starfab import get_starfab
from starfab.gui import qtc, qtw, qtg
from starfab.gui.widgets.common import TagBar
from starfab.gui.widgets.dcbrecord import DCBRecordItemView
from starfab.gui.widgets.dock_widgets.common import (
    StarFabSearchableTreeWidget,
    StarFabSearchableTreeFilterWidget,
)
from starfab.log import getLogger
from starfab.models.datacore import DCBSortFilterProxyModel, DCBItem
from starfab.utils import show_file_in_filemanager, reload_starfab_modules

logger = getLogger(__name__)


def _filter_tags(item, method, tags, tdb):
    if item.record is None:
        return False
    tags_to_check = set()
    item_tags = item.record.properties.get("tags", [])
    if isinstance(item_tags, StructureInstance):
        tags_to_check.update(
            str(tag)
            for _ in item_tags.properties.values()
            if (tag := tdb.tags_by_guid.get(str(_)) is not None)
        )
    else:
        tags_to_check.update(
            str(tag)
            for _ in item_tags
            if (tag := tdb.tags_by_guid.get(_.name)) is not None
        )
    return method(tag in tags for tag in tags_to_check)


class DCBFilterWidget(StarFabSearchableTreeFilterWidget):
    filter_types = {
        "has_any_tag": "Has Any Tag",
        "has_all_tags": "Has All Tags",
        "type": "Type",
    }

    filter_operators = {
        "and_": "And",
        "or_": "Or",
        "not_": "Not",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.h_layout = qtw.QHBoxLayout()
        self.setLayout(self.h_layout)
        self.setContentsMargins(1, 1, 1, 1)
        self.h_layout.setContentsMargins(1, 1, 1, 1)

        self.filter_op = qtw.QComboBox()
        for k, v in self.filter_operators.items():
            self.filter_op.addItem(v, userData=k)
        self.filter_op.currentIndexChanged.connect(self._handle_filter_updated)
        self.filter_op.setSizePolicy(qtw.QSizePolicy.Policy.Minimum, qtw.QSizePolicy.Policy.Minimum)
        self.filter_op.setFixedWidth(48)
        self.h_layout.addWidget(self.filter_op)

        self.filter_type = qtw.QComboBox()
        for k, v in self.filter_types.items():
            self.filter_type.addItem(v, userData=k)
        self.filter_type.currentIndexChanged.connect(self._handle_filter_type_changed)
        self.filter_type.setSizePolicy(qtw.QSizePolicy.Policy.Minimum, qtw.QSizePolicy.Policy.Minimum)
        self.filter_type.setFixedWidth(100)
        self.h_layout.addWidget(self.filter_type)

        self.tagbar = TagBar(self)
        self.tagbar.tags_updated.connect(self._handle_filter_updated)
        self.h_layout.addWidget(self.tagbar)

        starfab = get_starfab()
        if starfab.sc is not None:
            self._tag_completer = qtw.QCompleter(starfab.sc.tag_database.tag_names())
            self._tag_completer.setCaseSensitivity(qtc.Qt.CaseSensitivity.CaseInsensitive)
            self._tag_completer.setFilterMode(qtc.Qt.MatchFlag.MatchEndsWith)
            self._type_completer = qtw.QCompleter(
                sorted(starfab.sc.datacore.record_types)
            )
            self._type_completer.setCaseSensitivity(qtc.Qt.CaseSensitivity.CaseInsensitive)
            self._type_completer.setFilterMode(qtc.Qt.MatchFlag.MatchStartsWith)

        close_btn = qtw.QPushButton("-")
        close_btn.setFixedSize(24, 24)
        close_btn.setSizePolicy(qtw.QSizePolicy.Policy.Maximum, qtw.QSizePolicy.Policy.Maximum)
        close_btn.clicked.connect(self.close_filter)
        self.h_layout.addWidget(close_btn)

        self._handle_filter_type_changed(None)
        self.show()

    def compile_filter(self) -> (typing.Callable, typing.Callable):
        filter_type = self.filter_type.currentData()
        op = getattr(operator, self.filter_op.currentData())
        starfab = get_starfab()
        if not self.tagbar.tags or starfab.sc is None:
            return None
        elif filter_type == "has_any_tag":
            return op, partial(
                _filter_tags,
                method=any,
                tags=self.tagbar.tags,
                tdb=starfab.sc.tag_database,
            )
        elif filter_type == "has_all_tags":
            return op, partial(
                _filter_tags,
                method=all,
                tags=self.tagbar.tags,
                tdb=starfab.sc.tag_database,
            )
        elif filter_type == "type":
            return (
                op,
                lambda i, ts=self.tagbar.tags: i.record is not None
                and i.record.type in ts,
            )

    def _handle_filter_updated(self):
        self.filter_changed.emit()

    def _handle_filter_type_changed(self, index):
        filter_type = self.filter_type.currentData()
        self.tagbar.clear()
        if filter_type in ["has_any_tag", "has_all_tags"]:
            self.tagbar.valid_tags = get_starfab().sc.tag_database.tag_names()
            self.tagbar.line_edit.setCompleter(self._tag_completer)
        elif filter_type == "type":
            self.tagbar.valid_tags = list(get_starfab().sc.datacore.record_types)
            self.tagbar.line_edit.setCompleter(self._type_completer)
        self.filter_changed.emit()


class DCBTreeWidget(StarFabSearchableTreeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(proxy_model=DCBSortFilterProxyModel, *args, **kwargs)

        self.sc_tree_model = self.starfab.sc_manager.datacore_model
        self.starfab.sc_manager.datacore_model.loaded.connect(
            self._handle_datacore_loaded
        )

        self.proxy_model.setFilterKeyColumn(3)

        self.ctx_manager.default_menu.addSeparator()
        extract = self.ctx_manager.default_menu.addAction("Extract to...")
        extract.triggered.connect(partial(self.ctx_manager.handle_action, "extract"))
        extract = self.ctx_manager.menus[""].addAction("Extract to...")
        extract.triggered.connect(partial(self.ctx_manager.handle_action, "extract"))
        extract_all = self.ctx_manager.menus[""].addAction("Extract All...")
        extract_all.triggered.connect(
            partial(self.ctx_manager.handle_action, "extract_all")
        )
        copy_path = self.ctx_manager.menus[""].addAction("Copy Path")
        copy_path.triggered.connect(
            partial(self.ctx_manager.handle_action, "copy_path")
        )

        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(qtc.Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setSortCaseSensitivity(qtc.Qt.CaseSensitivity.CaseInsensitive)

        self.sc_add_filter.show()

    def _create_filter(self):
        return DCBFilterWidget(self)

    @qtc.Slot()
    def _handle_datacore_loaded(self):
        self.proxy_model.setSourceModel(self.sc_tree_model)
        self.sc_tree.setModel(self.proxy_model)
        self.proxy_model.sort(0, qtc.Qt.SortOrder.AscendingOrder)

        header = self.sc_tree.header()
        header.setSectionResizeMode(qtw.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, qtw.QHeaderView.ResizeMode.Stretch)
        self._sync_tree_header()

    def _handle_item_action(self, item, model, index):
        if os.environ.get("STARFAB_RELOAD_MODULES"):
            reload_starfab_modules("starfab.gui.widgets.dcbrecord")
            reload_starfab_modules("starfab.gui.widgets.common")
        if isinstance(item, DCBItem) and item.record is not None:
            widget = DCBRecordItemView(item, self.starfab)
            self.starfab.add_tab_widget(
                item.path, widget, item.name, tooltip=item.path.as_posix()
            )
            # TODO: error dialog

    def extract_items(self, items):
        items = [i for i in items if i.guid]
        edir = Path(qtw.QFileDialog.getExistingDirectory(self.starfab, "Extract to..."))
        if edir:
            total = len(items)
            self.starfab.task_started.emit(
                "extract_dcb", f"Extracting to {edir.name}", 0, total
            )
            t = time.time()
            for i, item in enumerate(items):
                if (time.time() - t) > 0.5:
                    self.starfab.update_status_progress.emit(
                        "extract_dcb", i, 0, total, f"Extracting records to {edir.name}"
                    )
                    t = time.time()
                try:
                    outfile = edir / item.path
                    outfile.parent.mkdir(parents=True, exist_ok=True)
                    if outfile.is_file():
                        outfile = (
                            outfile.parent
                            / f"{outfile.stem}.{item.guid}{outfile.suffix}"
                        )
                    with outfile.open("wb") as o:
                        shutil.copyfileobj(item.contents(), o)
                    qtg.QGuiApplication.processEvents()
                except Exception as e:
                    logger.exception(
                        f"Exception extracting record {item.path}", exc_info=e
                    )

            self.starfab.task_finished.emit("extract_dcb", True, "")
            show_file_in_filemanager(Path(edir))

    @qtc.Slot(str)
    def _on_ctx_triggered(self, action):
        selected_items = self.get_selected_items()
        if action == "extract":
            # Item Actions
            if not selected_items:
                return
            self.extract_items(selected_items)
        elif action == "extract_all":
            self.extract_items(self.sc_tree_model._guid_cache.values())
        elif action == "copy_path":
            qtg.QGuiApplication.clipboard().setText(selected_items[0].path.as_posix())
        else:
            return super()._on_ctx_triggered(action)
