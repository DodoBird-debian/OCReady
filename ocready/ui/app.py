import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ocready.ui.theme import app_icon, apply_theme
from ocready.ui.window import MainWindow


def run(image: str | None = None, edition: str = "pocket") -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("OCReady")
    app.setOrganizationName("OCReady")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = MainWindow(edition=edition)
    window.show()
    if image:
        QTimer.singleShot(100, lambda: window.open_path(image))
    return app.exec()
