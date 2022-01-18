import os
import sys
import ctypes
import asyncio
from pathlib import Path
import logging
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt, QCoreApplication
import qtvscodestyle as qtvsc


from . import __version__
from .settings import settings
from .app import MainWindow
from .log import setup_logging, getLogger
from .plugins import plugin_manager
from .resources import themes


logger = getLogger(__name__)


def exception_hook(exctype, value, traceback):
    # Catch PySide2 exceptions
    # https://stackoverflow.com/questions/43039048/pyqt5-fails-with-cryptic-message

    # Print the error and traceback
    logger.exception(f"Caught exception, exiting", exc_info=(exctype, value, traceback))
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


def main():
    plugin_manager.setup()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup_logging()

    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    if sys.executable.lower().endswith(
        "pythonw.exe"
    ) or sys.executable.lower().endswith("starfab.exe"):
        # on windows - if we're running as a "window" (wihtout a console) redirect stdout/stderr to files
        sys.stdout = open("starfab.out", "w")
        sys.stderr = open("starfab.err", "w")
    # else:
    #     # if we've got a console, log to it as well as the log file
    #     handler = logging.StreamHandler(sys.stdout)
    #     handler.setLevel(logging.DEBUG)
    #     handler.setFormatter(logging.Formatter(LOG_FMT))
    #     logging.getLogger().addHandler(handler)

    logger.info(f"StarFab {__version__}")
    if sys.platform == "win32":
        appid = "scdatatools.starfab"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setOrganizationName("scdatatools")
    app.setApplicationDisplayName(f"StarFab {__version__}")

    theme = settings.value("theme", "Monokai Dimmed")
    try:
        if theme in themes:
            app.setStyleSheet(qtvsc.load_stylesheet(themes[theme]))
    except Exception:
        logger.exception(
            f'Failed to load saved theme "{theme}", falling back to default'
        )
        app.setStyleSheet(qtvsc.load_stylesheet(themes['Monokai Dimmed']))
        settings.setValue("theme", "Monokai Dimmed")

    try:
        mw = MainWindow()
        mw.startup()

        sys.exit(app.exec_())
    except SystemExit:
        app.exit(0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
