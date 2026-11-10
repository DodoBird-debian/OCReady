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
    deadline = time.monotonic() + 8
    while window.worker and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert window.worker is None
    assert "مرحبا بالعالم" in window.editor.toPlainText()
    assert window.recognize_button.isEnabled()


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
