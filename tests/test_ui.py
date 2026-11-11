import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ocready.core.editions import EDITIONS
from ocready.core.pipeline import Request, recognize_image
from ocready.core.preprocess import Recipe
from ocready.engines.tesseract import readiness
from ocready.ui.theme import apply_theme
from ocready.ui.window import MainWindow


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    yield application


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    existing = set(app.topLevelWidgets())
    widget = MainWindow()
    widget.show()
    app.processEvents()
    yield widget
    for current in app.topLevelWidgets():
        if current in existing or not isinstance(current, MainWindow):
            continue
        if current.worker:
            current.worker.cancel.set()
            current.worker.wait(3000)
            app.processEvents()
        current.editor.document().setModified(False)
        current.close()
        current.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture
def recognized(window):
    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime to test real linked text")
    window.load_example()
    result, alternatives = recognize_image(window.source, Request(EDITIONS["pocket"], layout="sparse"))
    window._recognized(window.job, result, alternatives)
    return window


def test_empty_workspace_and_image_loading(window):
    assert not window.recognize_button.isEnabled()
    window.load_example()
    assert window.recognize_button.isEnabled()
    assert window.preview.size == (1100, 720)
    assert window.image_stack.currentWidget() is window.canvas


def test_workspace_uses_available_sans_fonts_including_the_text_editor(window):
    from PySide6.QtGui import QFontDatabase, QFontInfo

    available = {name.casefold() for name in QFontDatabase.families()}
    intended = {name.casefold() for name in ("Inter", "Segoe UI", "Noto Sans")}.intersection(available)
    if not intended:
        pytest.skip("This host uses its platform's general-font fallback")
    assert QFontInfo(window.font()).family().casefold() in intended
    assert QFontInfo(window.editor.font()).family().casefold() in intended


def test_real_clipboard_paste_reaches_bilingual_ocr_and_keeps_its_own_source(window, app):
    from PySide6.QtGui import QColor, QImage

    from ocready.core.paths import resource_root

    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime for real clipboard recognition")
    image = QImage(str(resource_root() / "assets/sample-bilingual.png"))
    QApplication.clipboard().setImage(image)
    assert window.paste_image()
    QApplication.clipboard().setText("Clipboard changed after paste")
    image.fill(QColor("black"))
    window.recognize()
    until = time.monotonic() + 10
    while window.worker and time.monotonic() < until:
        app.processEvents()
        time.sleep(.01)
    assert window.result and "مرحبا بالعالم" in window.result.text
    assert "screenshots" in window.editor.toPlainText() and window.editor.linked


def test_gui_smoke_does_not_cancel_vision_inside_its_engine_deadline(window, app, tmp_path, monkeypatch):
    import json
    import threading
    from types import SimpleNamespace

    from PySide6.QtCore import QTimer

    from ocready.core.models import ModelPack
    from ocready.core.types import OCRResult
    from ocready.ui import smoke

    # Accelerate only the diagnostic's scheduled deadlines. The simulated job
    # lasts 150 ms: longer than its former 120 s limit scaled by 1/1000.
    class AcceleratedTimer(QTimer):
        @staticmethod
        def singleShot(milliseconds, callback):
            QTimer.singleShot(max(1, milliseconds // 1000), callback)

    monkeypatch.setattr(smoke, "QTimer", AcceleratedTimer)
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    window.packs = [ModelPack("slow", "Slow English", "runner", "model", "projector", memory_mb=500, languages="eng")]
    window.refresh_methods()
    window.method_combo.setCurrentIndex(window.method_combo.findData("vision:slow"))
    window.vision_backend = "cpu"
    cancelled = threading.Event()

    def recognize():
        window.worker = SimpleNamespace(cancel=cancelled, wait=lambda _: True, isRunning=lambda: False)
        def complete():
            if getattr(window, "_smoke_done", False):
                return
            window._recognized(window.job, OCRResult("Expected text", engine="vision:slow", geometry="none"), [])
            window.worker = None
        QTimer.singleShot(150, complete)

    monkeypatch.setattr(window, "recognize", recognize)
    codes = []
    output = tmp_path / "smoke.json"
    smoke.attach_smoke_run(SimpleNamespace(exit=codes.append), window, None, output)
    until = time.monotonic() + 3
    while not output.exists() and time.monotonic() < until:
        app.processEvents()
        time.sleep(.005)
    record = json.loads(output.read_text(encoding="utf-8"))
    assert not cancelled.is_set() and codes == [0]
    assert record["text"] == "Expected text" and not record["error"]
    assert record["deadline_seconds"] > 300


def test_packaged_smoke_clicks_a_real_arabic_region_and_copies_text(window, app, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from ocready.ui.smoke import attach_smoke_run

    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime for the real copy workflow")
    output = tmp_path / "copy-smoke.json"
    original_read = Path.read_text
    def windows_default_encoding(path, *args, **kwargs):
        if path == output:
            kwargs.setdefault("encoding", "cp1252")
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", windows_default_encoding)
    codes = []
    attach_smoke_run(SimpleNamespace(exit=codes.append), window, None, output)
    until = time.monotonic() + 10
    while not output.exists() and time.monotonic() < until:
        app.processEvents()
        time.sleep(.01)
    record = json.loads(output.read_text(encoding="utf-8"))
    assert codes == [0] and not record["error"]
    assert record["source_selection_verified"] is True
    assert record["clipboard_copy_verified"] is True
    assert QApplication.clipboard().text() == record["text"]
    assert "مرحبا بالعالم" in record["text"]


def test_edition_method_layout_and_backend_choices_restore(window):
    from ocready.core.settings import save_settings
    save_settings({"edition": "studio", "methods": {"studio": "tesseract-fast", "everyday": "tesseract-best"},
                   "layout": "block", "vision_backend": "cpu"})
    restored = MainWindow()
    assert restored.edition.id == "studio"
    assert restored.method_combo.currentData() == "tesseract-fast"
    assert restored.layout_combo.currentData() == "block"
    assert restored.vision_backend == "cpu"
    restored.edition_combo.setCurrentIndex(restored.edition_combo.findData("everyday"))
    assert restored.method_combo.currentData() == "tesseract-best"
    restored.edition_combo.setCurrentIndex(restored.edition_combo.findData("studio"))
    assert restored.method_combo.currentData() == "tesseract-fast"
    restored.close()
    explicit = MainWindow(edition="pocket")
    assert explicit.edition.id == "pocket"
    assert explicit.method_combo.currentData() == "tesseract-fast"
    explicit.close()


def test_fresh_everyday_prefers_precision_and_build_restrictions_override_preferences(window, monkeypatch):
    fresh = MainWindow(edition="everyday")
    assert fresh.method_combo.currentData() == "tesseract-best"
    fresh.close()
    monkeypatch.setattr("ocready.ui.window.build_profile", lambda: {
        "edition": "pocket", "available_editions": ["pocket"], "methods": ["tesseract-fast"]})
    restricted = MainWindow()
    assert restricted.edition.id == "pocket"
    assert restricted.method_combo.currentData() == "tesseract-fast"
    restricted.close()


def test_gui_entrypoint_preserves_saved_edition_unless_explicitly_overridden(window, monkeypatch):
    from ocready.__main__ import main
    calls = []
    monkeypatch.setattr("ocready.ui.app.run", lambda image, edition, **_kwargs: calls.append(edition) or 17)
    assert main([]) == 17
    assert main(["--edition", "studio"]) == 17
    assert calls == [None, "studio"]


def test_explicit_gui_method_preserves_preferences_unless_requested(window):
    from ocready.core.models import ModelPack
    from ocready.core.types import OCRError
    from ocready.ui.app import select_method
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    original = window.method_combo.currentData()
    select_method(window, None)
    assert window.method_combo.currentData() == original
    window.packs = [ModelPack("small", "Small English", "runner", "model", "projector", memory_mb=500, languages="eng"),
                    ModelPack("large", "Large", "runner", "model", "projector", memory_mb=2800)]
    window.refresh_methods()
    select_method(window, "vision", "small")
    assert window.method_combo.currentData() == "vision:small"
    assert window.language_combo.currentData() == "eng"
    for invalid in ("missing", "large"):
        with pytest.raises(OCRError, match="unavailable"):
            select_method(window, "vision", invalid)
        assert window.method_combo.currentData() == "vision:small"
    select_method(window, "tesseract-fast")
    assert window.method_combo.currentData() == "tesseract-fast"


def test_cli_pack_selection_never_silently_uses_another_model(window, monkeypatch):
    from ocready.__main__ import main
    from ocready.core.models import ModelPack
    pack = ModelPack("available", "Available", "runner", "model", "projector", memory_mb=500, languages="eng")
    monkeypatch.setattr("ocready.core.models.load_packs", lambda: [pack])
    monkeypatch.setattr("ocready.core.pipeline.recognize_image", lambda *_args: pytest.fail("Must reject missing ID before inference"))
    assert main(["assets/sample-bilingual.png", "--edition", "everyday", "--method", "vision", "--pack-id", "missing", "--json"]) == 2
    assert main(["--method", "tesseract-fast", "--pack-id", "available"]) == 2


def test_gui_entrypoint_forwards_only_explicit_launch_choices(window, monkeypatch):
    from ocready.__main__ import main
    calls = []
    monkeypatch.setattr("ocready.ui.app.run", lambda *_args, **kwargs: calls.append(kwargs) or 0)
    assert main([]) == 0
    assert calls[-1]["options"].backend is None and calls[-1]["options"].layout is None
    assert calls[-1]["method"] is None
    assert main(["image.png", "--language", "eng", "--backend", "cpu", "--layout", "block",
                 "--model-pack", "model.json", "--invert", "--rotate", "90", "--threshold", "120"]) == 0
    options = calls[-1]["options"]
    assert calls[-1]["method"] == "vision"
    assert (options.language, options.backend, options.layout) == ("eng", "cpu", "block")
    assert options.recipe == Recipe(invert=True, rotation=90, threshold=120)
    assert options.model_pack == Path("model.json")
    assert main(["--neural-pack", "neural.json"]) == 0
    assert calls[-1]["method"] == "neural"
    before = len(calls)
    for arguments in (["--model-pack", "a", "--neural-pack", "b"],
                      ["--method", "tesseract-fast", "--model-pack", "a"],
                      ["--method", "vision", "--neural-pack", "a"], ["--invert"]):
        assert main(arguments) == 2
    assert len(calls) == before


@pytest.mark.parametrize("kind", ["vision", "neural"])
def test_gui_launch_imports_external_pack_without_installing_it(window, tmp_path, kind):
    import json

    from ocready.core.models import ModelPack
    from ocready.core.neural_packs import NeuralPack
    from ocready.core.paths import config_root
    from ocready.core.types import OCRError
    from ocready.ui.app import LaunchOptions, configure_launch

    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    for name in ("runner", "model", "projector", "detector", "recognizer", "dictionary"):
        (tmp_path / name).write_bytes(b"GGUF\n")
    if kind == "vision":
        pack = ModelPack("session", "Session English", "runner", "model", "projector", languages="eng", memory_mb=500)
    else:
        pack = NeuralPack("session", "Session English", "runner", "detector", "recognizer", "dictionary", languages="eng")
    manifest = tmp_path / "session.json"
    manifest.write_text(json.dumps(pack.to_dict()), encoding="utf-8")
    options = LaunchOptions(language="eng", backend="cpu", layout="block", **{
        "model_pack" if kind == "vision" else "neural_pack": manifest})
    configure_launch(window, options, kind)
    assert window.method_combo.currentData() == kind + ":session"
    assert window.language_combo.currentData() == "eng"
    assert window.layout_combo.currentData() == "block" and window.vision_backend == "cpu"
    loaded = next(p for p in (window.packs if kind == "vision" else window.neural_packs) if p.id == "session")
    assert loaded.runner == str((tmp_path / "runner").resolve())
    assert not (config_root() / ("models.json" if kind == "vision" else "neural-models.json")).exists()
    with pytest.raises(OCRError, match="unsupported"):
        configure_launch(window, LaunchOptions(language="ara"), kind, "session")


def test_gui_launch_cleanup_reaches_real_recognition_and_reset(window, app, tmp_path):
    from PIL import ImageOps

    from ocready.core.paths import resource_root
    from ocready.ui.app import LaunchOptions, configure_launch, open_launch_image

    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime for real launch workflow")
    from PIL import Image
    with Image.open(resource_root() / "assets/sample-bilingual.png") as original:
        dark = ImageOps.invert(original.convert("RGB")).transpose(Image.Transpose.ROTATE_180)
    image = tmp_path / "لقطة.png"
    dark.save(image)
    recipe = Recipe(invert=True, grayscale=True, autocontrast=True, rotation=180)
    configure_launch(window, LaunchOptions(language="ara+eng", backend="cpu", layout="sparse"), "tesseract-fast")
    open_launch_image(window, str(image), recipe)
    assert window.recipe == recipe and window.invert.isChecked() and window.gray.isChecked()
    assert window.auto_contrast.isChecked() and window.cleanup_button.isChecked()
    window.recognize()
    assert window.worker.request.recipe == recipe
    until = time.monotonic() + 10
    while window.worker and time.monotonic() < until:
        app.processEvents()
        time.sleep(.01)
    assert window.result and "مرحبا بالعالم" in window.result.text
    assert "screenshots" in window.editor.toPlainText()
    assert window.editor.linked
    window.reset_recipe()
    assert window.recipe == Recipe() and not window.invert.isChecked() and not window.gray.isChecked()
    assert not window.editor.linked and window.result is None


def test_rejected_gui_launch_does_not_overwrite_saved_preferences(window, app, monkeypatch):
    from ocready.core.models import ModelPack
    from ocready.core.paths import config_root
    from ocready.core.settings import save_settings
    from ocready.core.types import OCRError
    from ocready.ui.app import LaunchOptions, run

    save_settings({"edition": "studio", "language": "ara", "vision_backend": "cuda", "layout": "block"})
    settings = config_root() / "settings.json"
    before = settings.read_bytes()
    pack = ModelPack("english", "English", "runner", "model", "projector", languages="eng", memory_mb=500)
    monkeypatch.setattr("ocready.ui.window.load_packs", lambda: [pack])
    with pytest.raises(OCRError, match="unsupported"):
        run(edition="everyday", method="vision", pack_id="english", options=LaunchOptions(language="ara"))
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert settings.read_bytes() == before


def test_clicking_arabic_source_word_copies_logical_text(recognized, app):
    window = recognized
    index = next(i for i, word in enumerate(window.result.words) if word.text == "مرحبا")
    word = window.result.words[index]
    scene_point = window.canvas.rect_for(word.box).center()
    point = window.canvas.mapFromScene(scene_point)
    QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    assert window.canvas.selected == {index}
    assert window.editor.extraSelections()
    assert window.copy_selection.isEnabled()
    window.copy_image_selection()
    assert QApplication.clipboard().text() == "مرحبا"


def test_editor_selection_highlights_source_and_edits_invalidate(recognized, app):
    window = recognized
    cursor = window.editor.textCursor()
    cursor.setPosition(2)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    app.processEvents()
    assert window.canvas.selected
    window.editor.insertPlainText("edited")
    assert not window.editor.linked
    assert not window.canvas.words
    assert not window.copy_selection.isEnabled()
    assert "edited" in window.editor.toPlainText()


def test_reversible_cleanup_invalidates_geometry(recognized):
    window = recognized
    original = window.source.tobytes()
    window.recipe = Recipe(invert=True, rotation=90)
    window._apply_recipe()
    assert window.preview.size == (720, 1100)
    assert window.source.tobytes() == original
    assert not window.editor.linked
    window.reset_recipe()
    assert window.preview.tobytes() == original


def test_recognition_worker_returns_to_idle(window, app):
    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime to test background recognition")
    window.load_example()
    window.recognize()
    assert window.worker is not None
    assert not window.recognize_button.isEnabled()
    assert window.editor.isReadOnly()
    deadline = time.monotonic() + 8
    while window.worker and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert window.worker is None
    assert "مرحبا بالعالم" in window.editor.toPlainText()
    assert window.recognize_button.isEnabled()
    assert not window.editor.isReadOnly()


def test_busy_workspace_cannot_change_recipe_or_edit_text(window, monkeypatch):
    from ocready.core.types import Box
    from ocready.ui.settings import SettingsDialog
    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime to test background recognition")
    window.load_example()
    window.editor.setPlainText("Keep\nlines")
    window.editor.document().setModified(False)
    window.crop_button.setChecked(True)
    window.toggle_crop()
    window.recognize()
    recipe = window.worker.request.recipe
    preview = window.preview.size
    assert not window.canvas.crop_mode
    assert not window.view_original.isChecked()
    assert not window.view_original.isEnabled()
    assert not window.settings_button.isEnabled()
    assert not window.join_lines_button.isEnabled()
    window._crop_selected(Box(0, 0, 100, 100))
    window.join_lines()
    monkeypatch.setattr(SettingsDialog, "exec", lambda _self: pytest.fail("Settings opened during recognition"))
    window.show_settings()
    assert window.recipe == recipe
    assert window.preview.size == preview
    assert window.editor.toPlainText() == "Keep\nlines"
    window.cancel_recognition()


def test_ctrl_c_copies_source_words_without_replacing_editor_copy(recognized, app):
    window = recognized
    window.canvas.set_selection({0})
    window.canvas.setFocus()
    QTest.keyClick(window.canvas, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert QApplication.clipboard().text() == window.result.words[0].text
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.editor.setFocus()
    QTest.keyClick(window.editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text() == window.result.text[:5]


def test_recognition_flushes_a_pending_preview(window, app):
    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime to test background recognition")
    window.load_example()
    window.invert.setChecked(True)
    assert window.preview_timer.isActive()
    window.recognize()
    assert not window.preview_timer.isActive()
    assert window.preview.getpixel((0, 0)) == (0, 0, 0)
    window.cancel_recognition()


def test_stale_result_does_not_replace_new_document(recognized):
    window = recognized
    old = window.result
    window.editor.document().setModified(False)
    window.load_example()
    window._recognized(window.job - 1, old, [old])
    assert not window.editor.toPlainText()
    assert not window.canvas.words


def test_paste_image_from_native_clipboard(window, app):
    from PySide6.QtGui import QImage
    image = QImage(str(Path(__file__).resolve().parents[1] / "assets" / "sample-bilingual.png"))
    QApplication.clipboard().setImage(image)
    window.paste_image()
    assert window.source is not None
    assert window._source_name == "Clipboard image"


def test_settings_model_form_opens_without_a_configured_model(window, app):
    from PySide6.QtWidgets import QTabWidget

    from ocready.ui.settings import SettingsDialog
    dialog = SettingsDialog(window)
    dialog.findChild(QTabWidget).setCurrentIndex(1)
    dialog.resize(790, 560)
    dialog.show()
    app.processEvents()
    assert dialog.height() == 560
    scroll = dialog.findChild(QTabWidget).currentWidget()
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(dialog.prompt)
    app.processEvents()
    prompt_top = dialog.prompt.mapTo(scroll.viewport(), QPoint()).y()
    assert 0 <= prompt_top < scroll.viewport().height()
    assert dialog.fields["projector"].text() == ""
    assert dialog.memory.value() == 2800
    assert dialog.list.count() == 0
    dialog.accept()


def test_automatic_direction_is_independent_per_paragraph(window, app):
    from ocready.core.types import OCRResult
    text = "English text\nمرحبا بالعالم\n123 عربي"
    window.editor.set_result(OCRResult(text))
    first = window.editor.document().firstBlock()
    assert first.blockFormat().layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert first.next().blockFormat().layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert first.next().next().blockFormat().layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert window.editor.toPlainText() == text
    assert not window.editor.document().isModified()
    app.processEvents()
    cursor = window.editor.textCursor()
    cursor.setPosition(first.next().position())
    assert window.editor.cursorRect(cursor).x() > window.editor.viewport().width() / 2


def test_pasted_arabic_paragraphs_get_direction_with_one_undo(window, app):
    editor = window.editor
    editor.setPlainText("English")
    editor.document().setModified(False)
    editor.moveCursor(QTextCursor.MoveOperation.End)
    editor.insertPlainText("\nمرحبا بالعالم\nAnother line")
    app.processEvents()
    blocks = editor.document().firstBlock()
    assert blocks.blockFormat().layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert blocks.next().blockFormat().layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert blocks.next().next().blockFormat().layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert editor.document().isModified()
    editor.undo()
    assert editor.toPlainText() == "English"
    assert not editor.document().isModified()
    editor.redo()
    assert "مرحبا بالعالم" in editor.toPlainText()
    assert editor.document().firstBlock().next().blockFormat().layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_explicit_paragraph_direction_survives_arabic_edits(window):
    editor = window.editor
    editor.set_direction("ltr")
    editor.insertPlainText("مرحبا")
    assert editor.document().firstBlock().blockFormat().layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_original_image_keeps_located_word_selection_after_rotation(window, app):
    from ocready.core.types import Box, OCRResult, Word
    window.load_example()
    window.recipe = Recipe(rotation=90)
    window._apply_recipe()
    # For a clockwise turn, a source word at (100, 200, 80, 30) becomes this box.
    word = Word("مرحبا", Box(490, 100, 30, 80), 95, 0, 5, (1, 1, 1, 1))
    result = OCRResult("مرحبا", [word])
    window._recognized(window.job, result, [result])
    window.view_original.setChecked(True)
    window.toggle_original()
    assert window.canvas.words[0].box == Box(100, 200, 80, 30)
    point = window.canvas.mapFromScene(window.canvas.rect_for(window.canvas.words[0].box).center())
    QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    window.copy_image_selection()
    assert QApplication.clipboard().text() == "مرحبا"
    assert window.editor.linked
    for original in (False, True, False):
        window.view_original.setChecked(original)
        window.toggle_original()
        assert window.canvas.selected == {0}
        assert window.editor.extraSelections()
        assert window.copy_selection.isEnabled()
        window.copy_image_selection()
        assert QApplication.clipboard().text() == "مرحبا"


@pytest.mark.parametrize("geometry", ["word", "line"])
def test_text_selection_survives_original_processed_view_switch(window, app, geometry):
    from ocready.core.types import Box, OCRResult, Word
    window.load_example()
    window.recipe = Recipe(rotation=90)
    window._apply_recipe()
    result = OCRResult("مرحبا", [Word("مرحبا", Box(490, 100, 30, 80), 95, 0, 5)], geometry=geometry)
    window._recognized(window.job, result, [result])
    cursor = window.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    window.editor.setTextCursor(cursor)
    app.processEvents()
    assert window.canvas.selected == {0}
    for original in (True, False):
        window.view_original.setChecked(original)
        window.toggle_original()
        assert window.canvas.selected == {0}
        assert window.editor.textCursor().selectedText() == "مرحبا"
        assert window.canvas.words[0].box == (Box(100, 200, 80, 30) if original else result.words[0].box)
        window.copy_image_selection()
        assert QApplication.clipboard().text() == "مرحبا"


def _windows_capture_for_test(window, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    from ocready.ui.capture import CaptureController
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda _url: True)
    controller = CaptureController(window)
    controller.is_windows = True
    controller.clipboard_sequence = lambda: 10
    controller.capture_visible = lambda: None
    window.capture_controller = controller
    controller._launch()
    return controller


def test_capture_cancel_preserves_image_edits_and_maximized_state(window, app):
    from ocready.ui.capture import CaptureController
    window.load_example()
    window.editor.insertPlainText("نسخة معدلة")
    source = window.source
    window.showMaximized()
    app.processEvents()
    controller = CaptureController(window)
    window.capture_controller = controller
    window.hide()
    controller.cancel()
    assert window.source is source
    assert window.editor.toPlainText() == "نسخة معدلة"
    assert window.editor.document().isModified()
    assert window.windowState() & Qt.WindowState.WindowMaximized
    assert not controller.path.exists()
    assert window.capture_controller is None


def test_spectacle_output_is_imported_then_deleted(window):
    from PySide6.QtCore import QProcess

    from ocready.ui.capture import CaptureController
    controller = CaptureController(window)
    window.capture_controller = controller
    fixture = Path(__file__).resolve().parents[1] / "assets" / "sample-bilingual.png"
    controller.path.write_bytes(fixture.read_bytes())
    controller._spectacle_finished(0, QProcess.ExitStatus.NormalExit)
    assert controller.done
    assert window.source.size == (1100, 720)
    assert window._source_name == "Captured region"
    assert not controller.path.exists()


def test_windows_capture_ignores_old_clipboard_generation(window, monkeypatch):
    from PySide6.QtGui import QImage
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    QApplication.clipboard().setImage(image)
    controller = _windows_capture_for_test(window, monkeypatch)
    controller._clipboard_changed()
    assert window.source is None
    assert not controller.done
    controller.clipboard_sequence = lambda: 11
    controller._clipboard_changed()
    assert controller.done
    assert window.source.size == (20, 20)


def test_failed_windows_snip_keeps_dirty_text_and_reports_import_error(window, monkeypatch):
    from PySide6.QtGui import QImage
    window.load_example()
    window.editor.insertPlainText("Keep my edits")
    source = window.source
    controller = _windows_capture_for_test(window, monkeypatch)
    controller.clipboard_sequence = lambda: 11
    image = QImage(3000, 2000, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    QApplication.clipboard().setImage(image)
    assert controller.done
    assert window.source is source
    assert window.editor.toPlainText() == "Keep my edits"
    assert window.editor.document().isModified()
    assert "too large" in window.status.text()


def test_windows_capture_returns_after_observed_host_closes(window, monkeypatch):
    controller = _windows_capture_for_test(window, monkeypatch)
    state = {"visible": True, "now": 0.0}
    controller.capture_visible = lambda: state["visible"]
    controller.clock = lambda: state["now"]
    controller._poll_capture_host()
    state["visible"] = False
    controller._poll_capture_host()
    state["now"] = 1.4
    controller._poll_capture_host()
    assert not controller.done
    state["now"] = 1.6
    controller._poll_capture_host()
    assert controller.done
    assert "cancelled" in window.status.text()


def test_unknown_windows_capture_host_does_not_false_cancel(window, monkeypatch):
    controller = _windows_capture_for_test(window, monkeypatch)
    controller.capture_visible = lambda: False
    controller.clock = lambda: 100.0
    controller._poll_capture_host()
    assert not controller.done
    controller.cancel()


def test_vision_text_can_be_copied_without_fabricating_source_boxes(window):
    from ocready.core.types import OCRResult
    window.load_example()
    result = OCRResult("Read this text", engine="vision:example")
    window._recognized(window.job, result, [result])
    window.copy_all()
    assert QApplication.clipboard().text() == "Read this text"
    assert not window.editor.linked
    assert not window.boxes.isEnabled()
    assert window.link_status.text() == "AI transcription"


def test_neural_result_selects_and_copies_whole_detected_lines(window, app):
    from ocready.core.types import Box, OCRResult, Word
    window.load_example()
    text = "مرحبا بالعالم"
    line = Word(text, Box(100, 200, 300, 60), 93, 0, len(text), (1, 1, 1, 1))
    result = OCRResult(text, [line], engine="neural:test", geometry="line")
    window._recognized(window.job, result, [result])
    assert window.boxes.text() == "Line boxes"
    assert window.link_status.text() == "Linked lines"
    point = window.canvas.mapFromScene(window.canvas.rect_for(line.box).center())
    QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    assert window.canvas.selected == {0}
    window.copy_image_selection()
    assert QApplication.clipboard().text() == text
    assert "line" in window.status.text()
    assert window.editor.extraSelections()
    window.editor.insertPlainText("edited")
    assert not window.canvas.words
    assert not window.boxes.isEnabled()


def test_neural_pack_options_and_method_selection(window, tmp_path):
    from ocready.core.neural_packs import NeuralPack
    from ocready.ui.neural_settings import NeuralSettings
    assets = []
    for name in ("runner", "detector", "recognizer", "dictionary"):
        path = tmp_path / name
        path.write_text("a\nb\n")
        assets.append(str(path))
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    window.neural_packs = [NeuralPack("test", "Neural test", *assets)]
    window.refresh_methods()
    window.method_combo.setCurrentIndex(window.method_combo.findData("neural:test"))
    assert not window.layout_combo.isEnabled()
    assert not window.compare_check.isEnabled()
    settings = NeuralSettings(window)
    settings.direction.setCurrentIndex(settings.direction.findData("ltr"))
    settings.memory.setValue(350)
    settings.save_options()
    assert window.neural_packs[0].direction == "ltr"
    assert window.neural_packs[0].memory_mb == 350
    settings.close()
    settings.deleteLater()


def test_alternative_reads_update_text_geometry_and_preserve_unsaved_edits(window, monkeypatch):
    from ocready.core.types import Box, OCRResult, Word
    window.load_example()
    shorter = OCRResult("مرحبا", [Word("مرحبا", Box(20, 30, 80, 40), 97, 0, 5)], layout="auto")
    complete = OCRResult("مرحبا بالعالم", [Word("مرحبا", Box(40, 50, 80, 40), 91, 0, 5),
                                          Word("بالعالم", Box(130, 50, 100, 40), 90, 6, 13)], layout="sparse")
    window._recognized(window.job, shorter, [shorter, complete])
    assert window.alternatives_bar.isVisible()
    assert window.alternatives_combo.count() == 2
    window.canvas.set_selection({0})
    window._image_selected({0})
    window.alternatives_combo.setCurrentIndex(1)
    assert window.result is complete
    assert window.editor.toPlainText() == complete.text
    assert window.canvas.words == complete.words
    assert not window.canvas.selected
    assert not window.copy_selection.isEnabled()
    assert not window.editor.extraSelections()
    window.copy_all()
    assert QApplication.clipboard().text() == complete.text
    window.editor.insertPlainText("edited")
    edited = window.editor.toPlainText()
    monkeypatch.setattr(window, "_confirm_replace", lambda: False)
    window.alternatives_combo.setCurrentIndex(0)
    assert window.alternatives_combo.currentIndex() == 1
    assert window.editor.toPlainText() == edited
    assert window.editor.document().isModified()
    monkeypatch.setattr(window, "_confirm_replace", lambda: True)
    window.alternatives_combo.setCurrentIndex(0)
    assert window.editor.toPlainText() == shorter.text
    window.rotate_image()
    assert not window.alternatives_bar.isVisible()
    assert not window.alternatives
    assert window.alternatives_combo.count() == 0


def test_worker_exposes_real_layout_alternatives_without_restarting_inference(window, app):
    if not readiness()[0]:
        pytest.skip("Prepare OCR runtime to test comparison readings")
    window.load_example()
    window.compare_check.setChecked(True)
    window.recognize()
    assert not window.alternatives_combo.isEnabled()
    deadline = time.monotonic() + 10
    while window.worker and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert window.worker is None
    assert {result.layout for result in window.alternatives} == {"sparse", "block"}
    assert window.alternatives_combo.count() == 2
    index = 1 - window.alternatives_combo.currentIndex()
    chosen = window.alternatives[index]
    window.alternatives_combo.setCurrentIndex(index)
    assert window.result is chosen
    assert window.editor.toPlainText() == chosen.text
    assert window.worker is None
    window.editor.document().setModified(False)
    window.load_example()
    assert not window.alternatives_bar.isVisible()


def test_vision_preview_matches_engine_input_and_preserves_original(window, monkeypatch):
    from PIL import Image

    from ocready.core.models import ModelPack
    from ocready.core.types import OCRResult
    from ocready.engines import vision
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    pack = ModelPack("compact", "Compact", "runner", "model", "projector", memory_mb=500,
                     languages="eng", max_pixels=500_000, max_edge=1000)
    window.packs = [pack]
    window.refresh_methods()
    source = Image.new("RGB", (2400, 1800), (20, 30, 40))
    window._set_source(source, "Large screenshot")
    full_size = window.preview.size
    window.method_combo.setCurrentIndex(window.method_combo.findData("vision:compact"))
    assert window.preview.width * window.preview.height <= pack.max_pixels
    assert max(window.preview.size) <= pack.max_edge
    assert window.view_original.isEnabled()
    assert window.source is source
    window.recipe = Recipe(invert=True, rotation=90, threshold=100)
    window._apply_recipe()
    expected = window.preview.copy()

    def read_image(path, *_args, **_kwargs):
        with Image.open(path) as image:
            assert image.size == expected.size
            assert image.tobytes() == expected.tobytes()
        return OCRResult("transcribed", engine="vision:compact")

    monkeypatch.setattr(vision, "recognize", read_image)
    recognize_image(source, Request(window.edition, "eng", "vision:compact", recipe=window.recipe, model_pack=pack))
    assert source.getpixel((0, 0)) == (20, 30, 40)
    window.reset_recipe()
    window.method_combo.setCurrentIndex(window.method_combo.findData("tesseract-fast"))
    assert window.preview.size == full_size


def test_model_image_limits_survive_settings_edits(window, tmp_path):
    from ocready.core.models import ModelPack
    from ocready.ui.settings import SettingsDialog
    for name in ("model", "projector"):
        (tmp_path / name).write_bytes(b"GGUFdata")
    runner = tmp_path / "runner"
    runner.write_text("test")
    pack = ModelPack("compact", "Compact", str(runner), str(tmp_path / "model"), str(tmp_path / "projector"),
                     memory_mb=500, max_pixels=750_000, max_edge=1200)
    window.packs = [pack]
    dialog = SettingsDialog(window)
    dialog.select_pack(0)
    assert dialog.pixels.value() == 750
    assert dialog.edge.value() == 1200
    dialog.edge.setValue(1024)
    dialog.save_model()
    assert window.packs[0].max_pixels == 750_000
    assert window.packs[0].max_edge == 1024
    dialog.close()


def test_external_vision_runtime_can_be_swapped_in_native_settings(window, tmp_path):
    from ocready.ui.settings import SettingsDialog
    runner, model = tmp_path / "runner", tmp_path / "model.onnx"
    runner.write_bytes(b"runner")
    model.write_bytes(b"opaque model")
    dialog = SettingsDialog(window)
    dialog.new_pack()
    dialog.name.setText("Custom offline vision")
    dialog.adapter.setCurrentIndex(dialog.adapter.findData("json-cli-v1"))
    dialog.fields["runner"].setText(str(runner))
    dialog.fields["model"].setText(str(model))
    dialog.fields["projector"].clear()
    dialog.save_model()
    pack = next(p for p in window.packs if p.name == "Custom offline vision")
    assert pack.adapter == "json-cli-v1" and pack.projector == ""
    dialog.select_pack(next(i for i, p in enumerate(dialog.packs) if p.id == pack.id))
    assert dialog.adapter.currentData() == "json-cli-v1"
    dialog.close()


def test_switching_limited_models_restores_user_language_choice(window):
    from ocready.core.models import ModelPack
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    window.packs = [ModelPack("english", "English model", "runner", "model", "projector", memory_mb=500, languages="eng"),
                    ModelPack("arabic", "Arabic model", "runner", "model", "projector", memory_mb=500, languages="ara")]
    window.refresh_methods()
    window.language_combo.setCurrentIndex(window.language_combo.findData("ara+eng"))
    window.method_combo.setCurrentIndex(window.method_combo.findData("vision:english"))
    assert window.language_combo.currentData() == "eng"
    assert not window.language_combo.model().item(window.language_combo.findData("ara")).isEnabled()
    window.method_combo.setCurrentIndex(window.method_combo.findData("tesseract-best"))
    assert window.language_combo.currentData() == "ara+eng"
    assert all(window.language_combo.model().item(i).isEnabled() for i in range(window.language_combo.count()))
    window.language_combo.setCurrentIndex(window.language_combo.findData("eng"))
    window.method_combo.setCurrentIndex(window.method_combo.findData("vision:arabic"))
    assert window.language_combo.currentData() == "ara"
    window.method_combo.setCurrentIndex(window.method_combo.findData("tesseract-best"))
    assert window.language_combo.currentData() == "eng"


def test_model_language_constraint_does_not_overwrite_saved_preference(window):
    from ocready.core.models import ModelPack
    from ocready.core.settings import load_settings
    window.edition_combo.setCurrentIndex(window.edition_combo.findData("everyday"))
    window.packs = [ModelPack("english", "English model", "runner", "model", "projector", memory_mb=500, languages="eng")]
    window.refresh_methods()
    window.method_combo.setCurrentIndex(window.method_combo.findData("vision:english"))
    assert window.language_combo.currentData() == "eng"
    window.close()
    assert load_settings()["language"] == "ara+eng"
