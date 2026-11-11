import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
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
    widget = MainWindow()
    widget.show()
    app.processEvents()
    yield widget
    if widget.worker:
        widget.worker.cancel.set()
        widget.worker.wait(3000)
        app.processEvents()
    widget.editor.document().setModified(False)
    widget.close()
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
    from ocready.ui.settings import SettingsDialog
    dialog = SettingsDialog(window)
    dialog.show()
    app.processEvents()
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
