"""
 Based on https://github.com/marcel-goldschen-ohm/PyQtImageViewer/blob/master/QtImageViewer.py
"""

import sys
import struct
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageQt
from qtpy.QtCore import Slot, Signal

from starfab.gui import qtc, qtg, qtw
from starfab.utils import image_converter
from starfab.gui.utils import ScrollMessageBox

from scdatatools.engine.textures.dds import unsplit_dds

Image.init()
SUPPORTED_IMG_FORMATS = list(Image.EXTENSION.keys())
DDS_CONV_FORMAT = "png"


class QImageViewer(qtw.QGraphicsView):
    """PyQt image viewer widget for a QPixmap in a QGraphicsView scene with mouse zooming and panning.
    Displays a QImage or QPixmap (QImage is internally converted to a QPixmap).
    To display any other image format, you must first convert it to a QImage or QPixmap.
    Some useful image format conversion utilities:
        qimage2ndarray: NumPy ndarray <==> QImage    (https://github.com/hmeine/qimage2ndarray)
        ImageQt: PIL Image <==> QImage  (https://github.com/python-pillow/Pillow/blob/master/PIL/ImageQt.py)
    Mouse interaction:
        Left mouse button drag: Pan image.
        Right mouse button drag: Zoom box.
        Right mouse button doubleclick: Zoom to show entire image.
    """

    # Mouse button signals emit image scene (x, y) coordinates.
    # !!! For image (row, column) matrix indexing, row = y and column = x.
    leftMouseButtonPressed = Signal(qtc.QPointF)
    rightMouseButtonPressed = Signal(qtc.QPointF)
    leftMouseButtonReleased = Signal(qtc.QPointF)
    rightMouseButtonReleased = Signal(qtc.QPointF)
    leftMouseButtonDoubleClicked = Signal(qtc.QPointF)
    rightMouseButtonDoubleClicked = Signal(qtc.QPointF)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Image is displayed as a QPixmap in a QGraphicsScene attached to this QGraphicsView.
        self.scene = qtw.QGraphicsScene()
        self.setScene(self.scene)

        self.setTransformationAnchor(qtw.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(qtw.QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(qtw.QFrame.NoFrame)
        self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(qtg.QBrush(qtg.QColor(30, 30, 30)))
        self.setContextMenuPolicy(qtc.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._handle_ctx_menu)

        self.ctx_menu = qtw.QMenu()
        self.act_save_as = self.ctx_menu.addAction("Save As...")
        self.act_save_as.triggered.connect(self._handle_save_as)

        # Store a local handle to the scene's current image pixmap.
        self.image = qtw.QGraphicsPixmapItem()
        self.scene.addItem(self.image)

        # Scroll bar behaviour.
        #   Qt.ScrollBarAlwaysOff: Never shows a scroll bar.
        #   Qt.ScrollBarAlwaysOn: Always shows a scroll bar.
        #   Qt.ScrollBarAsNeeded: Shows a scroll bar only when zoomed.
        self.setHorizontalScrollBarPolicy(qtc.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(qtc.Qt.ScrollBarAsNeeded)

        self._empty = True
        self._zoom = 0

    @Slot(qtc.QPointF)
    def _handle_ctx_menu(self, pos):
        self.act_save_as.setEnabled(self.hasImage())
        self.ctx_menu.exec_(self.mapToGlobal(pos))

    @Slot()
    def _handle_save_as(self):
        if not self.hasImage():
            return
        img_formats = qtg.QImageReader.supportedImageFormats()
        text_filter = "Images ({})".format(
            " ".join([f"*.{_.data().decode('utf-8')}" for _ in img_formats])
        )
        save_path, _ = qtw.QFileDialog.getSaveFileName(
            self, "Save Image As...", filter=text_filter
        )
        if save_path:
            # TODO: handle setting quality
            # TODO: handle confirm overwrite
            self.image.pixmap().save(save_path)

    def hasImage(self):
        """Returns whether or not the scene contains an image pixmap."""
        return not self._empty

    def fitInView(self, scale=True):
        rect = qtc.QRectF(self.image.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)  # Set scene size to image size.
            if self.hasImage():
                unity = self.transform().mapRect(qtc.QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(
                    viewrect.width() / scenerect.width(),
                    viewrect.height() / scenerect.height(),
                )
                self.scale(factor, factor)
                self._zoom = 0

    def setImage(self, image):
        """Set the scene's current image pixmap to the input QImage or QPixmap.
        Raises a RuntimeError if the input image has type other than QImage or QPixmap.
        :type image: QImage | QPixmap
        """
        self._zoom = 0
        if isinstance(image, qtg.QPixmap):
            pixmap = image
        elif isinstance(image, qtg.QImage):
            pixmap = qtg.QPixmap.fromImage(image)
        else:
            raise ValueError(
                "QImageViewer.setImage: Argument must be a QImage or QPixmap."
            )
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)
            self.image.setPixmap(pixmap)
        else:
            self._empty = True
            self.setDragMode(qtw.QGraphicsView.NoDrag)
            self.image.setPixmap(qtg.QPixmap())
        self.fitInView()

    def wheelEvent(self, event):
        if self.hasImage():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1
            else:
                factor = 0.8
                self._zoom -= 1
            if self._zoom > 0:
                self.scale(factor, factor)
            elif self._zoom == 0:
                self.fitInView()
            else:
                self._zoom = 0

    def toggleDragMode(self):
        if self.dragMode() == qtw.QGraphicsView.ScrollHandDrag:
            self.setDragMode(qtw.QGraphicsView.NoDrag)
        elif not self._photo.pixmap().isNull():
            self.setDragMode(qtw.QGraphicsView.ScrollHandDrag)

    def mousePressEvent(self, event):
        if self.image.isUnderMouse():
            pos = self.mapToScene(event.pos())
            if event.button() == qtc.Qt.LeftButton:
                self.leftMouseButtonPressed.emit(pos)
            elif event.button() == qtc.Qt.RightButton:
                self.rightMouseButtonPressed.emit(pos)
        super().mousePressEvent(event)

    @classmethod
    def fromFile(cls, fp, *args, **kwargs):
        iv = QImageViewer(*args, **kwargs)
        iv.load_from_file(fp)
        return iv

    def load_from_file(self, fp):
        try:
            image = qtg.QImage.fromData(fp.read())
            if image.format() == qtg.QImage.Format_Invalid:
                # Try Pillow
                fp.seek(0)
                img = Image.open(fp)
                image = ImageQt.ImageQt(img)
        except Exception as e:
            ScrollMessageBox.critical(self, "Image Viewer", f"Cannot load {fp}: {e}")
            return False
        self.setImage(image)
        return True


class DDSImageViewer(qtw.QWidget):
    def __init__(self, dds_files, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            self.dds_header = next(
                iter(v for k, v in dds_files.items() if k.lower().endswith(".dds"))
            )
        except StopIteration:
            raise ValueError(f"Could not determine the DDS header file")

        # self.dds_files.remove(self.dds_header)
        # # unsplit files should be largest to smallest
        #
        # hdr_data = self.dds_header.contents().getvalue()
        # dds_magic, dds_hdr_len = struct.unpack('<4sI', hdr_data[:8])
        # dds_hdr_len += 4  # does not include the magic bytes
        # if dds_magic != b'DDS ':
        #     raise ValueError(f'Invalid DDS header')
        #
        # self.dds_file = hdr_data[:dds_hdr_len]
        # if self.dds_files:
        #     self.dds_files = sorted(self.dds_files, key=lambda d: d.path.suffix, reverse=True)
        #     for d in self.dds_files:
        #         self.dds_file += d.contents().getvalue()
        # self.dds_file += hdr_data[dds_hdr_len:]

        layout = qtw.QVBoxLayout()
        image = QImageViewer()

        try:
            dds_file = unsplit_dds({p: i.info for p, i in dds_files.items()})
            data = BytesIO(
                image_converter.convert_buffer(dds_file, "dds", DDS_CONV_FORMAT)
            )
            if not image.load_from_file(data):
                raise RuntimeError
        except RuntimeError as e:
            raise RuntimeError(f"Error parsing {self.dds_header.path}: {e}")
        layout.addWidget(image)
        self.setLayout(layout)
