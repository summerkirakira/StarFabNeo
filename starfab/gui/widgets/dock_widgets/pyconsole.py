import scdatatools
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager

from starfab import __version__
from starfab.gui import qtw, qtg, qtc


BANNER = f"""starfab {__version__} console
scdatatools {scdatatools.__version__}

Local variables:
    starfab       -  The starfab application
    starfab.sc    -  The currently loaded StarCitizen

"""


class PyConsoleDockWidget(qtw.QDockWidget):
    def __init__(self, starfab, *args, **kwargs):
        super().__init__(parent=starfab, *args, **kwargs)
        self.starfab = starfab
        self.setAllowedAreas(
            qtc.Qt.DockWidgetArea.BottomDockWidgetArea |
            qtc.Qt.DockWidgetArea.RightDockWidgetArea |
            qtc.Qt.DockWidgetArea.LeftDockWidgetArea
        )

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = "qt"
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.kernel_manager.kernel.shell.push(
            {
                "starfab": starfab,
                "scdatatools": scdatatools,
            }
        )

        self.ipython_widget = RichJupyterWidget()
        self.ipython_widget.kernel_manager = self.kernel_manager
        self.ipython_widget.kernel_client = self.kernel_client
        self.ipython_widget.set_default_style("linux")
        self.ipython_widget.banner = BANNER
        self.ipython_widget.kernel_banner = ""

        self.setWidget(self.ipython_widget)

    def closeEvent(self, event) -> None:
        self.starfab.actionConsole.setChecked(False)
        super().closeEvent(event)
