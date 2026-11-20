"""Keep explicit runner checks off the UI thread."""
import threading

from PySide6.QtCore import QThread, Signal

from ocready.core.types import Cancelled
from ocready.engines.vision_checks import check_model_backends


class BackendCheckWorker(QThread):
    reportReady = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, generation, pack, edition, parent=None):
        super().__init__(parent)
        self.generation = generation
        self.pack = pack
        self.edition = edition
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            report = check_model_backends(self.pack, self.edition, cancel=self.cancel)
            if not self.cancel.is_set():
                self.reportReady.emit(self.generation, report)
        except Cancelled:
            pass
        except Exception as exc:
            self.failed.emit(self.generation, str(exc) or type(exc).__name__)


def report_text(report: dict) -> str:
    if report["cpu_available"]:
        cpu = "CPU runner responds."
    elif report["cpu_runner"]["status"] == "responding":
        cpu = "The CPU runner does not declare CPU support."
    else:
        cpu = "CPU runner unavailable: " + report["cpu_runner"]["detail"]
    if report["cuda_device_detected"]:
        cuda = "CUDA device detected; model inference still needs testing."
    elif report["cuda_runner"]["status"] != "responding":
        cuda = "CUDA unavailable: " + report["cuda_runner"]["detail"]
    else:
        cuda = "No CUDA device reported."
    assets = "" if report["assets_valid"] else "\nModel files: " + report["assets_error"]
    return cpu + "\n" + cuda + assets + "\n" + report["admission"] + "\nThis check does not load model weights."
