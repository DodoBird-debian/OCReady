import threading

from PIL import Image
from PySide6.QtCore import QThread, Signal

from ocready.core.pipeline import Request, recognize_image


class RecognitionWorker(QThread):
    resultReady = Signal(int, object, object)
    failed = Signal(int, str)
    progress = Signal(str)

    def __init__(self, job: int, image: Image.Image, request: Request, parent=None):
        super().__init__(parent)
        self.job = job
        self.image = image
        self.request = request
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            result, alternatives = recognize_image(self.image, self.request, cancel=self.cancel,
                                                   progress=self.progress.emit)
            self.resultReady.emit(self.job, result, alternatives)
        except Exception as exc:
            self.failed.emit(self.job, str(exc) or type(exc).__name__)
        finally:
            # Do not keep old full-size image buffers alive in a finished QObject.
            self.image = None
