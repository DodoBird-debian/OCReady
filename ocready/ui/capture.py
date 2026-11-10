import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from ocready.core.capture_api import capture_host_visible, clipboard_sequence
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
        self.is_windows = sys.platform == "win32"
        self.clipboard_sequence = clipboard_sequence
        self.capture_visible = capture_host_visible
        self.clock = time.monotonic
        self._connected = False
        self._seen_capture_host = False
        self._left_host_at = None
        self.previous_window_state = window.windowState()
        self.activity = QTimer(self)
        self.activity.setInterval(150)
        self.activity.timeout.connect(self._poll_capture_host)

    def start(self) -> None:
        self.previous_window_state = self.window.windowState()
        self.window.hide()
        self.timer.start(90_000)
        QTimer.singleShot(250, self._launch)

    def _launch(self) -> None:
        if self.done:
            return
        if self.is_windows:
            self.sequence = self.clipboard_sequence()
            QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
            self._connected = True
            self.activity.start()
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
        if self.done or not self.is_windows:
            return
        sequence = self.clipboard_sequence()
        if sequence == self.sequence or QApplication.clipboard().image().isNull():
            return
        # The user already agreed to replace the current document before opening capture.
        imported = self.window.paste_image(replace_confirmed=True)
        self.finish("Region captured. Choose Recognize text." if imported else self.window.status.text())

    def _poll_capture_host(self) -> None:
        if self.done:
            return
        visible = self.capture_visible()
        if visible is True:
            self._seen_capture_host = True
            self._left_host_at = None
        elif visible is False and self._seen_capture_host:
            now = self.clock()
            if self._left_host_at is None:
                self._left_host_at = now
            elif now - self._left_host_at >= 1.5:
                self._clipboard_changed()
                if not self.done:
                    self.cancel()

    def cancel(self) -> None:
        self.finish("Capture cancelled. Your previous image and text are still here.")

    def finish(self, message: str) -> None:
        if self.done:
            return
        self.done = True
        self.timer.stop()
        self.activity.stop()
        if self._connected:
            try:
                QApplication.clipboard().dataChanged.disconnect(self._clipboard_changed)
            except RuntimeError:
                pass
            self._connected = False
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        self.directory.cleanup()
        self.window.setWindowState(self.previous_window_state)
        self.window.show()
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
    try:
        controller = CaptureController(window)
        window.capture_controller = controller
        controller.start()
    except OSError:
        window._set_status("Could not prepare a screenshot file. Check temporary-folder access and available space.", error=True)
