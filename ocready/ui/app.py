import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ocready.ui.theme import app_icon, apply_theme
from ocready.ui.window import MainWindow


def run(image: str | None = None, edition: str = "pocket", *, smoke_output: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("OCReady")
    app.setOrganizationName("OCReady")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = MainWindow(edition=edition)
    window.show()
    if smoke_output:
        from ocready.ui.smoke import attach_smoke_run
        attach_smoke_run(app, window, image, smoke_output)
    elif image:
        QTimer.singleShot(100, lambda: window.open_path(image))
    return app.exec()
