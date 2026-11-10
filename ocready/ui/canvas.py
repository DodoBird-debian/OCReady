from PIL import Image
from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from ocready.core.types import Box, Word


class ImageCanvas(QGraphicsView):
    wordsSelected = Signal(object)
    cropSelected = Signal(object)
    zoomChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setFrameShape(self.Shape.NoFrame)
        self.setBackgroundBrush(QColor("#edf1f7"))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(self.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.setMinimumSize(260, 220)
        self.setAccessibleName("Source image. Click a word or drag over text to select it.")
        self.words: list[Word] = []
        self.selected: set[int] = set()
        self.show_boxes = False
        self.crop_mode = False
        self._start = None
        self._rubber = None
        self._pan: QPoint | None = None
        self._pixmap = None
        self._fit = True
        self._hover = -1

    def set_image(self, image: Image.Image) -> None:
        rgb = image.convert("RGB")
        raw = rgb.tobytes()
        qimage = QImage(raw, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()
        self.scene().clear()
        self._pixmap = self.scene().addPixmap(QPixmap.fromImage(qimage))
        self.scene().setSceneRect(QRectF(0, 0, rgb.width, rgb.height))
        self.words, self.selected = [], set()
        self._rubber = self._start = None
        self.fit_image()

    def set_words(self, words: list[Word]) -> None:
        self.words = words
        self.selected = set()
        self.viewport().update()

    def set_selection(self, indices: set[int]) -> None:
        self.selected = indices
        self.viewport().update()

    def fit_image(self) -> None:
        if self._pixmap:
            self.fitInView(self.sceneRect().adjusted(-22, -22, 22, 22), Qt.AspectRatioMode.KeepAspectRatio)
            self._fit = True
            self.zoomChanged.emit(round(self.transform().m11() * 100))

    def zoom(self, factor: float) -> None:
        scale = self.transform().m11() * factor
        if .03 <= scale <= 12:
            self.scale(factor, factor)
            self._fit = False
            self.zoomChanged.emit(round(scale * 100))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit:
            self.fit_image()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap:
            self.zoom(1.16 if event.angleDelta().y() > 0 else 1 / 1.16)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._start = self.mapToScene(event.position().toPoint())
            self._rubber = QRectF(self._start, self._start)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan is not None:
            position = event.position().toPoint()
            delta = position - self._pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan = position
        elif self._start is not None:
            self._rubber = QRectF(self._start, self.mapToScene(event.position().toPoint())).normalized()
            self.viewport().update()
        else:
            point = self.mapToScene(event.position().toPoint())
            hover = next((i for i, w in enumerate(self.words) if self.rect_for(w.box).contains(point)), -1)
            if hover != self._hover:
                self._hover = hover
                self.setCursor(Qt.CursorShape.IBeamCursor if hover >= 0 else Qt.CursorShape.ArrowCursor)
                self.viewport().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            self.unsetCursor()
        elif event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            rect = self._rubber.intersected(self.sceneRect())
            if self.crop_mode:
                if rect.width() >= 4 and rect.height() >= 4:
                    self.cropSelected.emit(Box(int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())))
            else:
                if rect.width() < 4 and rect.height() < 4:
                    rect = QRectF(self._start.x() - 1, self._start.y() - 1, 2, 2)
                self.selected = {i for i, w in enumerate(self.words) if self.rect_for(w.box).intersects(rect)}
                self.wordsSelected.emit(self.selected)
            self._start = self._rubber = None
            self.viewport().update()
        else:
            super().mouseReleaseEvent(event)

    @staticmethod
    def rect_for(box: Box) -> QRectF:
        return QRectF(box.x, box.y, box.width, box.height)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        for i, word in enumerate(self.words):
            if i not in self.selected and i != self._hover and not self.show_boxes:
                continue
            box = self.rect_for(word.box)
            if not box.intersects(rect):
                continue
            selected = i in self.selected
            pen = QPen(QColor("#386bdf" if selected else "#8ca9d3"))
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QColor(56, 107, 223, 55 if selected else 12))
            painter.drawRoundedRect(box.adjusted(-2, -2, 2, 2), 2, 2)
        if self._rubber:
            pen = QPen(QColor("#386bdf"))
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(56, 107, 223, 25))
            painter.drawRect(self._rubber)
