import sys
import ctypes
import asyncio
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt

import qtmodern.styles

from . import __version__
from .app import MainWindow

import logging
logging.basicConfig(filename='scdv.log', filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S', level=logging.INFO)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    # Catch PySide2 exceptions
    # https://stackoverflow.com/questions/43039048/pyqt5-fails-with-cryptic-message

    # Print the error and traceback
    print(exctype, value, traceback)
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook
logging.info(f'SCDV {__version__}')
if sys.executable.lower().endswith('pythonw.exe') or sys.executable.lower().endswith('scdv.exe'):
    sys.stdout = open('scdv.out', 'w')
    sys.stderr = open('scdv.err', 'w')


def main():
    if sys.platform == 'win32':
        appid = u'scdatatools.scdv'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    app = QApplication(sys.argv)
    app.setOrganizationName('scdatatools')
    app.setApplicationDisplayName(f'SCDV {__version__}')
    app.setAttribute(Qt.AA_EnableHighDpiScaling)

    try:
        # qtmodern.styles.dark(app)
        mw = MainWindow()
        mw.set_dark_theme()
        mw.show()

        sys.exit(app.exec_())
    except SystemExit:
        app.exit(0)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
