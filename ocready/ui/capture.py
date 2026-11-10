import ctypes
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from ocready.core.images import load_image


class CaptureController(QObject):
    """Own exactly one capture, including its subprocess, timer and temp path."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.directory = tempfile.TemporaryDirectory(prefix="ocready-capture-")
        self.path = Path(self.directory.name) / "capture.png"
        self.process = QProcess(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.finish("Capture cancelled or timed out. Your previous image is still here."))
        self.done = False
        self.sequence = 0

    def start(self) -> None:
        self.window.hide()
        self.timer.start(90_000)
        QTimer.singleShot(250, self._launch)

    def _launch(self) -> None:
        if self.done:
            return
        if sys.platform == "win32":
            self.sequence = ctypes.windll.user32.GetClipboardSequenceNumber()
            QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
            # Unpackaged Win32 applications use clipboard return, never an MSIX redirect callback.
            if not QDesktopServices.openUrl(QUrl("ms-screenclip:")):
                self.finish("Could not open Snipping Tool. Press Win+Shift+S, then use Paste image.")
        else:
            spectacle = shutil.which("spectacle")
            if not spectacle:
                self.finish("KDE Spectacle is not installed. Use your screenshot tool, then choose Paste image.")
                return
            environment = QProcessEnvironment.systemEnvironment()
            # A bundled Qt runtime must not leak its plugin paths into the system's Spectacle.
            for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "LD_LIBRARY_PATH"):
                environment.remove(key)
            self.process.setProcessEnvironment(environment)
            self.process.finished.connect(self._spectacle_finished)
            self.process.errorOccurred.connect(lambda _error: self.finish("Could not start Spectacle. Capture a screenshot manually, then paste it."))
            self.process.start(spectacle, ["--region", "--background", "--nonotify", "--output", str(self.path)])

    def _spectacle_finished(self, code: int, _status) -> None:
        if self.done:
            return
        if code == 0 and self.path.is_file():
            try:
                image = load_image(self.path, self.window.edition)
                self.window._set_source(image, "Captured region")
                self.finish("Region captured. Choose Recognize text.")
            except Exception as exc:
                self.finish(str(exc))
        else:
            self.finish("Capture cancelled. Your previous image is still here.")

    def _clipboard_changed(self) -> None:
        if self.done or sys.platform != "win32":
            return
        sequence = ctypes.windll.user32.GetClipboardSequenceNumber()
        if sequence == self.sequence or QApplication.clipboard().image().isNull():
            return
        # The user already agreed to replace the current document before opening capture.
        self.window.editor.document().setModified(False)
        self.window.paste_image()
        self.finish("Region captured. Choose Recognize text.")

    def finish(self, message: str) -> None:
        if self.done:
            return
        self.done = True
        self.timer.stop()
        if sys.platform == "win32":
            try:
                QApplication.clipboard().dataChanged.disconnect(self._clipboard_changed)
            except RuntimeError:
                pass
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        self.directory.cleanup()
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        self.window._set_status(message)
        self.window.capture_controller = None
        self.deleteLater()


def start_capture(window) -> None:
    if window.worker or getattr(window, "capture_controller", None):
        return
    if not window._confirm_replace():
        return
    if os.name != "nt" and not shutil.which("spectacle"):
        window._set_status("Install KDE Spectacle, or take a screenshot with your desktop tool and use Paste image.")
        return
    controller = CaptureController(window)
    window.capture_controller = controller
    controller.start()
