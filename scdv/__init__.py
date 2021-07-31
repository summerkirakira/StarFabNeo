import sys
from pathlib import Path

from qtpy.QtWidgets import QApplication, QMainWindow

CONTRIB_DIR = Path(__file__).parent / 'contrib'
__version__ = '0.3.5'


if CONTRIB_DIR.is_dir() and str(CONTRIB_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRIB_DIR))


def get_scdv():
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                return widget
    return None
