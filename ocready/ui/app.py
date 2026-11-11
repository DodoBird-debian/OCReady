import sys
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ocready.core.preprocess import Recipe
from ocready.core.types import OCRError
from ocready.ui.theme import app_icon, apply_theme
from ocready.ui.window import MainWindow


@dataclass(frozen=True)
class LaunchOptions:
    language: str | None = None
    backend: str | None = None
    layout: str | None = None
    model_pack: Path | None = None
    neural_pack: Path | None = None
    compare: bool = False
    recipe: Recipe = field(default_factory=Recipe)


def configure_launch(window: MainWindow, options: LaunchOptions, method: str | None,
                     pack_id: str | None = None) -> None:
    """Apply explicit launch choices; imported packs exist only in this session."""
    if options.model_pack:
        from ocready.core.models import load_pack
        pack = load_pack(options.model_pack)
        pack.validate()
        window.packs = [p for p in window.packs if p.id != pack.id] + [pack]
        pack_id = pack.id
    if options.neural_pack:
        from ocready.core.neural_packs import load_neural_pack
        pack = load_neural_pack(options.neural_pack)
        pack.validate()
        window.neural_packs = [p for p in window.neural_packs if p.id != pack.id] + [pack]
        pack_id = pack.id
    if options.model_pack or options.neural_pack:
        window.refresh_methods()
    select_method(window, method, pack_id)
    if options.language:
        index = window.language_combo.findData(options.language)
        if index < 0 or not window.language_combo.model().item(index).isEnabled():
            raise OCRError("The requested language is unsupported by the selected model. Choose another language or method.")
        window.language_combo.setCurrentIndex(index)
        window._preferred_language = options.language
    if options.backend:
        window.vision_backend = options.backend
    if options.layout:
        window.layout_combo.setCurrentIndex(window.layout_combo.findData(options.layout))
    if options.compare:
        window.compare_check.setChecked(True)


def open_launch_image(window: MainWindow, image: str, recipe: Recipe) -> None:
    if window.open_path(image) and recipe != Recipe():
        window.set_recipe(recipe)
        window.cleanup_button.setChecked(True)


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
        method: str | None = None, pack_id: str | None = None, options: LaunchOptions | None = None) -> int:
    options = options or LaunchOptions()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("OCReady")
    app.setOrganizationName("OCReady")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = MainWindow(edition=edition)
    try:
        configure_launch(window, options, method, pack_id)
    except (OCRError, OSError, ValueError):
        # An invalid launch must not save partially applied preferences.
        window.deleteLater()
        raise
    window.show()
    if smoke_output:
        from ocready.ui.smoke import attach_smoke_run
        attach_smoke_run(app, window, image, smoke_output, recipe=options.recipe)
    elif image:
        QTimer.singleShot(100, lambda: open_launch_image(window, image, options.recipe))
    return app.exec()
