import os
import sys
import ctypes
import asyncio
import logging
from pathlib import Path
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt

from . import __version__
from .app import MainWindow
from .log import setup_logging, logger, LOG_FMT


def exception_hook(exctype, value, traceback):
    # Catch PySide2 exceptions
    # https://stackoverflow.com/questions/43039048/pyqt5-fails-with-cryptic-message

    # Print the error and traceback
    logger.exception(f'Caught exception, exiting', exc_info=(exctype, value, traceback))
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup_logging()

    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    if sys.executable.lower().endswith('pythonw.exe') or sys.executable.lower().endswith('scdv.exe'):
        # on windows - if we're running as a "window" (wihtout a console) redirect stdout/stderr to files
        sys.stdout = open('scdv.out', 'w')
        sys.stderr = open('scdv.err', 'w')
    else:
        # if we've got a console, log to it as well as the log file
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(LOG_FMT))
        logging.getLogger().addHandler(handler)

    logger.info(f'SCDV {__version__}')
    if sys.platform == 'win32':
        appid = u'scdatatools.scdv'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setOrganizationName('scdatatools')
    app.setApplicationDisplayName(f'SCDV {__version__}')

    try:
        mw = MainWindow()
        mw.show()

        sys.exit(app.exec_())
    except SystemExit:
        app.exit(0)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
