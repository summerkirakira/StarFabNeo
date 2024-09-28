import os
import sys
import ctypes
import asyncio

import sentry_sdk
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt, QCoreApplication

# TODO: Figure out what this is for, it's not being handled by poetry as a dependency by default.
import qtvscodestyle as qtvsc


from . import __version__
from .app import StarFab
from .resources import themes
from .settings import settings
from .plugins import plugin_manager
from .log import setup_logging, getLogger
from starfab.error import sentry_error_handler

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
    setup_logging()

    sentry_sdk.init(
        "https://6827c55631754b76a98f2cfc6374933e@o1159851.ingest.sentry.io/6244166",
        debug=logger.logger.getEffectiveLevel() <= 10,  # logging is DEBUG or more
        release=os.environ.get("STARFAB_SENTRY_RELEASE", __version__),
        traces_sample_rate=float(os.environ.get('STARFAB_TRACES_SAMPLE_RATE', 1.0)),
        server_name="StarFab",
        before_send=sentry_error_handler
    )

    plugin_manager.setup()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

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
        mw = StarFab()
        mw.startup()

        sys.exit(app.exec_())
    except SystemExit:
        app.exit(0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
