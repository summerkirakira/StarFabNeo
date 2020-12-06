from io import BytesIO
from pathlib import Path

from PIL import Image, ImageQt

from scdv.ui import qtc, qtg, qtw

Image.init()
SUPPORTED_IMG_FORMATS = list(Image.EXTENSION.keys())


class QImageViewer(qtw.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scaleFactor = 0.0

        self.imageLabel = qtw.QLabel()
        self.imageLabel.setBackgroundRole(qtg.QPalette.Base)
        self.imageLabel.setSizePolicy(qtw.QSizePolicy.Ignored, qtw.QSizePolicy.Ignored)
        self.imageLabel.setScaledContents(True)

        self.scrollArea = qtw.QScrollArea()
        self.scrollArea.setBackgroundRole(qtg.QPalette.Dark)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setVisible(False)

        layout = qtw.QVBoxLayout()
        layout.addWidget(self.scrollArea)
        self.setLayout(layout)

        self.ctx_menu = qtw.QMenu()
        self.zoomInAct = self.ctx_menu.addAction("Zoom In (25%)")
        self.zoomInAct.triggered.connect(self.zoomIn)
        self.zoomOutAct = self.ctx_menu.addAction("Zoom Out (25%)")
        self.zoomOutAct.triggered.connect(self.zoomOut)
        self.normalSizeAct = self.ctx_menu.addAction("Normal Size")
        self.normalSizeAct.triggered.connect(self.normalSize)
        self.fitToWindowAct = self.ctx_menu.addAction("Fit to Window")
        self.fitToWindowAct.setCheckable(True)
        self.fitToWindowAct.triggered.connect(self.fitToWindow)

        self.setContextMenuPolicy(qtc.Qt.CustomContextMenu)

        self.image = None

    @classmethod
    def fromFile(cls, fp, *args, **kwargs):
        iv = QImageViewer(*args, **kwargs)
        if iv.load_from_file(fp):
            return iv
        return None


    def customMenuEvent(self, event):
        self.ctx_menu.exec_(event.globalPos())

    def open(self):
        options = qtw.QFileDialog.Options()

        # fileName = QFileDialog.getOpenFileName(self, "Open File", QDir.currentPath())
        fileName, _ = qtw.QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '',
                                                      'Images (*.png *.jpeg *.jpg *.bmp *.gif)', options=options)
        return self.load_from_file(str(Path(fileName)))

    def load_from_file(self, fp):
        try:
            image = qtg.QImage.fromData(fp.read())
            if image.format() == qtg.QImage.Format_Invalid:
                # Try Pillow
                fp.seek(0)
                img = Image.open(fp)
                image = ImageQt.ImageQt(img)
        except Exception as e:
            qtw.QMessageBox.information(self, "Image Viewer", f"Cannot load {fp}: {e}")
            return False
        return self.load_qimage(image)

    def load_qimage(self, image):
        self.image = image
        self.imageLabel.setPixmap(qtg.QPixmap.fromImage(self.image))
        self.scaleFactor = 1.0

        self.scrollArea.setVisible(True)
        self.fitToWindowAct.setEnabled(True)
        self.updateActions()

        if not self.fitToWindowAct.isChecked():
            self.imageLabel.adjustSize()
        return True

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def normalSize(self):
        self.imageLabel.adjustSize()
        self.scaleFactor = 1.0

    def fitToWindow(self):
        fitToWindow = self.fitToWindowAct.isChecked()
        self.scrollArea.setWidgetResizable(fitToWindow)
        if not fitToWindow:
            self.normalSize()

        self.updateActions()

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

    def scaleImage(self, factor):
        self.scaleFactor *= factor
        self.imageLabel.resize(self.scaleFactor * self.imageLabel.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                               + ((factor - 1) * scrollBar.pageStep() / 2)))
