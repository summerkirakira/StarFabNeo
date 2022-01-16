from functools import partial

from starfab.gui import qtc, qtw, qtg


class CollapsableWidget(qtw.QFrame):
    def __init__(self, label, expand=False, layout=qtw.QFormLayout, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.expanded = expand
        self.setObjectName('CollapseableWidget')

        self.main_layout = qtw.QVBoxLayout()
        self.setStyleSheet("""
        QFrame#CollapseableWidget {
            border: 1px solid #555;
        }
        """)
        self.main_layout.setMargin(0)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.expand_button = qtw.QPushButton(label)
        self.expand_button.setStyleSheet('text-align: left; padding-left: 5px; border-radius: 0px; ')

        self.content = qtw.QWidget()
        self.content.setLayout(layout())
        self.main_layout.addWidget(self.expand_button, 0, qtc.Qt.AlignTop)
        self.main_layout.addWidget(self.content, 0, qtc.Qt.AlignTop)
        self.expand_button.clicked.connect(self.toggle)
        self.setLayout(self.main_layout)

        self.expand_button.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.expand_button.customContextMenuRequested.connect(self._show_ctx_menu)

        if expand:
            self.expand()
        else:
            self.collapse()

    def subObjects(self):
        subs = []
        for child in self.content.children():
            for cw in child.findChildren(qtw.QWidget, 'CollapseableWidget'):
                subs.append(cw)
        return subs

    def filter(self, text, ignore_case=True):
        if not text:
            _ = True
        elif any(_.filter(text) for _ in self.subObjects()):
            _ = True
        elif ignore_case:
            _ = text.lower() in self.expand_button.text().lower()
        else:
            _ = text in self.expand_button.text()
        self.setVisible(_)
        return _

    def collapse(self):
        self.content.hide()
        self.expand_button.setText(f'⯈ {self.label}')
        self.expanded = False

    def collapse_all(self):
        self.collapse()
        for so in self.subObjects():
            so.collapse_all()

    def expand(self):
        self.content.show()
        self.expand_button.setText(f'▼  {self.label}')
        self.expanded = True

    def expand_all(self):
        self.expand()
        for so in self.subObjects():
            so.expand_all()

    def toggle(self):
        if self.expanded:
            self.collapse()
        else:
            self.expand()

    def _build_ctx_menu(self):
        menu = qtw.QMenu()
        if self.expanded:
            collapse = menu.addAction('Collapse')
            collapse.triggered.connect(self.collapse)
            collapse_all = menu.addAction('Collapse All')
            collapse_all.triggered.connect(self.collapse_all)
        else:
            expand = menu.addAction('Expand')
            expand.triggered.connect(self.expand)
        expand_all = menu.addAction('Expand All')
        expand_all.triggered.connect(self.expand_all)
        return menu

    def _show_ctx_menu(self, pos):
        self._build_ctx_menu().exec_(self.expand_button.mapToGlobal(pos))


class FlowLayout(qtw.QLayout):
    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        super(FlowLayout, self).__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        del self._items[:]

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self):
        if self._hspacing >= 0:
            return self._hspacing
        else:
            return self.smartSpacing(
                qtw.QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspacing >= 0:
            return self._vspacing
        else:
            return self.smartSpacing(
                qtw.QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)

    def expandingDirections(self):
        return qtc.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(qtc.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = qtc.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += qtc.QSize(left + right, top + bottom)
        return size

    def doLayout(self, rect, testonly):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        lineheight = 0
        for item in self._items:
            widget = item.widget()
            hspace = self.horizontalSpacing()
            if hspace == -1:
                hspace = widget.style().layoutSpacing(
                    qtw.QSizePolicy.PushButton,
                    qtw.QSizePolicy.PushButton, qtc.Qt.Horizontal)
            vspace = self.verticalSpacing()
            if vspace == -1:
                vspace = widget.style().layoutSpacing(
                    qtw.QSizePolicy.PushButton,
                    qtw.QSizePolicy.PushButton, qtc.Qt.Vertical)
            nextX = x + item.sizeHint().width() + hspace
            if nextX - hspace > effective.right() and lineheight > 0:
                x = effective.x()
                y = y + lineheight + vspace
                nextX = x + item.sizeHint().width() + hspace
                lineheight = 0
            if not testonly:
                item.setGeometry(
                    qtc.QRect(qtc.QPoint(x, y), item.sizeHint()))
            x = nextX
            lineheight = max(lineheight, item.sizeHint().height())
        return y + lineheight - rect.y() + bottom

    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()


class TagBar(qtw.QFrame):
    tag_added = qtc.Signal(str)
    tag_removed = qtc.Signal(str)
    tags_updated = qtc.Signal()

    def __init__(self, valid_tags=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Tag Bar')
        self.setObjectName('TagBar')
        self.tags = []
        self.valid_tags = valid_tags or []
        self.setStyleSheet("""
        QFrame#TagBar {
          background: palette(base);
          border: 1px solid palette(alternate-base);
        }

        QFrame#TagBar:focus {
          background: palette(base);
          border: 1px solid palette(highlight);
        }

        QFrame#Tag {
            border:1px solid palette(highlight); 
            border-radius: 4px;
            background-color: palette(alternate-base);
        }

        QFrame#Tag > QLabel {
            color: palette(highlighted-text);
            border: 0;
        }

        QFrame#Tag > QPushButton {
            color: palette(highlighted-text);
            border: 0;
            font-weight: bold;
        }

        QFrame#Tag:focus {
            border:1px solid palette(alternate-base); 
            border-radius: 4px;
        }

        QLineEdit {
            border: 0;
        }
        """)
        self.setFrameShape(qtw.QFrame.Box)
        self.setFrameShadow(qtw.QFrame.Plain)
        self.setAutoFillBackground(True)
        # self.h_layout = FlowLayout()
        self.h_layout = qtw.QHBoxLayout()
        self.h_layout.setSpacing(4)
        self.setLayout(self.h_layout)
        self.line_edit = qtw.QLineEdit()
        self.line_edit.setSizePolicy(qtw.QSizePolicy.Minimum, qtw.QSizePolicy.Maximum)
        self.line_edit.setStyleSheet("border: 0;")
        if self.valid_tags:
            completer = qtw.QCompleter(valid_tags)
            self.line_edit.setCompleter(completer)
            completer.activated.connect(self.create_tags)
        self.setSizePolicy(qtw.QSizePolicy.Minimum, qtw.QSizePolicy.Minimum)
        self.setContentsMargins(1, 1, 1, 1)
        self.h_layout.setContentsMargins(1, 1, 1, 1)
        self.line_edit.returnPressed.connect(self.create_tags)
        self.line_edit.installEventFilter(self)
        self.refresh()

    def eventFilter(self, obj, event):
        if obj == self.line_edit and event.type() == qtc.QEvent.KeyPress and event.key() == qtc.Qt.Key_Tab:
            self.create_tags()
            return True
        return super().eventFilter(obj, event)

    def create_tags(self):
        for tag in self.line_edit.text().split(','):
            tag = tag.strip()
            if tag and tag not in self.tags and (not self.valid_tags or tag in self.valid_tags):
                self.tag_added.emit(tag)
                self.tags.append(tag)
        self.tags = sorted(set(self.tags))
        self.line_edit.setText('')
        self.refresh()

    def clear(self):
        self.tags = []
        self.line_edit.setText('')
        self.refresh()

    def refresh(self):
        for i in reversed(range(self.h_layout.count())):
            widget = self.h_layout.takeAt(i).widget()
            widget.setParent(None)
            if widget != self.line_edit:
                del widget
        for tag in self.tags:
            self.add_tag_to_bar(tag)
        self.h_layout.addWidget(self.line_edit)
        self.line_edit.setFocus()
        self.tags_updated.emit()

    def add_tag_to_bar(self, text):
        tag = qtw.QFrame(self)
        tag.setObjectName('Tag')
        tag.setContentsMargins(0, 0, 0, 0)
        tag.setFixedHeight(18)
        hbox = qtw.QHBoxLayout()
        hbox.setContentsMargins(2, 2, 2, 2)
        hbox.setSpacing(10)
        tag.setLayout(hbox)
        label = qtw.QLabel(text)
        label.setFixedHeight(12)
        hbox.addWidget(label)
        x_button = qtw.QPushButton('x')
        x_button.setFixedSize(10, 10)
        x_button.setSizePolicy(qtw.QSizePolicy.Maximum, qtw.QSizePolicy.Maximum)
        x_button.clicked.connect(partial(self.delete_tag, text))
        hbox.addWidget(x_button)
        tag.setSizePolicy(qtw.QSizePolicy.Maximum, qtw.QSizePolicy.Preferred)
        self.h_layout.addWidget(tag)
        self.tag_added.emit(text)

    def delete_tag(self, tag_name):
        self.tags.remove(tag_name)
        self.tag_removed.emit(tag_name)
        self.refresh()

