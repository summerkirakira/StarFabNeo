import sys
import typing
from pathlib import Path

from qtpy.QtWidgets import QApplication, QMainWindow

if typing.TYPE_CHECKING:
    from starfab.app import StarFab

CONTRIB_DIR = Path(__file__).parent / "contrib"
__version__ = "0.4.9"


if CONTRIB_DIR.is_dir() and str(CONTRIB_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRIB_DIR))


def get_starfab() -> 'StarFab':
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                return widget
    return None
