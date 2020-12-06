import sys

import scdatatools
import IPython
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager

from scdv import __version__
from scdv.ui import qtw, qtg, qtc


BANNER = f"""scdv console {__version__}
scdatatools {__version__}

Local variables:
  scdv  -  The scdv Qt MainWindow
  sc    -  The currently opened StarCitizen

"""


class PyConsoleDockWidget(qtw.QDockWidget):
    def __init__(self, scdv, *args, **kwargs):
        super().__init__(parent=scdv, *args, **kwargs)

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.kernel_manager.kernel.shell.push({
            'scdv': scdv,
            'scdatatools': scdatatools,
            'sc': scdv.sc
        })

        self.ipython_widget = RichJupyterWidget()
        self.ipython_widget.kernel_manager = self.kernel_manager
        self.ipython_widget.kernel_client = self.kernel_client
        self.ipython_widget.set_default_style('linux')
        self.ipython_widget.banner = BANNER
        self.ipython_widget.kernel_banner = ''

        self.setWidget(self.ipython_widget)
