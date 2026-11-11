import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ocready.core.types import OCRError
from ocready.ui.theme import app_icon, apply_theme
from ocready.ui.window import MainWindow


def select_method(window: MainWindow, method: str | None, pack_id: str | None = None) -> None:
    if not method:
        return
    key = method
    if method in {"vision", "neural"}:
        default = window.profile.get("default_model" if method == "vision" else "default_neural")
        preferred = window.method_combo.findData(f"{method}:{pack_id or default}")
        index = preferred if preferred >= 0 else next((i for i in range(window.method_combo.count())
                    if str(window.method_combo.itemData(i)).startswith(method + ":")
                    and window.method_combo.model().item(i).isEnabled()), -1)
        if pack_id:
            index = window.method_combo.findData(f"{method}:{pack_id}")
    else:
        index = window.method_combo.findData(key)
    if index < 0 or not window.method_combo.model().item(index).isEnabled():
        raise OCRError("The requested OCR method or pack is unavailable in this edition. Check Settings and its memory requirements.")
    window.method_combo.setCurrentIndex(index)


def run(image: str | None = None, edition: str | None = None, *, smoke_output: Path | None = None,
        method: str | None = None, pack_id: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("OCReady")
    app.setOrganizationName("OCReady")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = MainWindow(edition=edition)
    try:
        select_method(window, method, pack_id)
    except OCRError:
        window.close()
        raise
    window.show()
    if smoke_output:
        from ocready.ui.smoke import attach_smoke_run
        attach_smoke_run(app, window, image, smoke_output)
    elif image:
        QTimer.singleShot(100, lambda: window.open_path(image))
    return app.exec()
