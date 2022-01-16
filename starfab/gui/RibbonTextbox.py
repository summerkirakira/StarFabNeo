from qtpy.QtWidgets import QLineEdit

class RibbonTextbox(QLineEdit):
    def __init__(self, default_value, min_width=50, max_width=50, change_connector=False, read_only=True):
        QLineEdit.__init__(self)
        self.setStyleSheet("border: 1px solid rgba(0,0,0,30%);")
        self.setText(default_value)
        self.setReadOnly(read_only)
        self.setMinimumWidth(min_width)
        self.setMaximumWidth(max_width)
        if change_connector:
            self.textChanged.connect(change_connector)
