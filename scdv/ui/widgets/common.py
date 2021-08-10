from scdv.ui import qtc, qtw, qtg


class CollapseableWidget(qtw.QFrame):
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
        self.expand_button.setStyleSheet('text-align: left; padding-left: 5px; border-radius: 0px; background: #555;')

        self.content = qtw.QWidget()
        self.content.setLayout(layout())
        self.main_layout.addWidget(self.expand_button, 0, qtc.Qt.AlignTop)
        self.main_layout.addWidget(self.content, 0, qtc.Qt.AlignTop)
        self.expand_button.clicked.connect(self.toggle)
        self.setLayout(self.main_layout)

        if expand:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        self.content.hide()
        self.expand_button.setText(f'▼  {self.label}')
        self.expanded = False

    def expand(self):
        self.content.show()
        self.expand_button.setText(f'▲  {self.label}')
        self.expanded = True

    def toggle(self):
        if self.expanded:
            self.collapse()
        else:
            self.expand()
