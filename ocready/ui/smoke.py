"""Diagnostic path for testing the actual compiled native GUI without QtTest."""
import json
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QApplication

from ocready.core.memory import tree_rss
from ocready.core.preprocess import Recipe
from ocready.core.timeouts import gui_workload_timeout_seconds


def attach_smoke_run(app, window, image: str | None, output: Path, *, recipe: Recipe | None = None) -> None:
    started = False
    deadline = gui_workload_timeout_seconds(str(window.method_combo.currentData()), backend=window.vision_backend,
                                           compare=window.compare_check.isChecked())

    def start():
        nonlocal started
        if image:
            window.open_path(image)
        else:
            window.load_example()
        if recipe is not None and window.source is not None:
            window.set_recipe(recipe)
        window.recognize()
        started = True

    def finish(error: str = ""):
        if getattr(window, "_smoke_done", False):
            return
        window._smoke_done = True
        window._smoke_timer.stop()
        if window.worker:
            window.worker.cancel.set()
            window.worker.wait(5000)
        result = window.result
        copied = None
        source_selected = None
        if not error and result and window.editor.toPlainText():
            try:
                if result.words:
                    index = next((i for i, word in enumerate(result.words)
                                  if any("\u0600" <= char <= "\u06ff" for char in word.text)), 0)
                    point = window.canvas.mapFromScene(window.canvas.rect_for(window.canvas.words[index].box).center())
                    viewport = window.canvas.viewport()
                    for kind, buttons in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                                          (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
                        event = QMouseEvent(kind, QPointF(point), QPointF(viewport.mapToGlobal(point)),
                                            Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
                        QApplication.sendEvent(viewport, event)
                    if window.canvas.selected != {index} or not window.editor.extraSelections():
                        raise ValueError("Clicking the detected region did not link its text selection.")
                    window.copy_image_selection()
                    if QApplication.clipboard().text() != result.words[index].text:
                        raise ValueError("The selected source text did not reach the clipboard correctly.")
                    source_selected = True
                window.copy_all()
                copied = QApplication.clipboard().text() == window.editor.toPlainText()
                if not copied:
                    raise ValueError("Copy all did not preserve the displayed Unicode text.")
            except Exception as exc:
                error = f"GUI copy check failed: {exc}"
        output.parent.mkdir(parents=True, exist_ok=True)
        record = {"text": window.editor.toPlainText(), "words": len(window.canvas.words),
                  "linked": window.editor.linked, "rss": tree_rss(), "error": error, "deadline_seconds": deadline,
                  "qt_platform": QGuiApplication.platformName(), "clipboard_copy_verified": copied,
                  "source_selection_verified": source_selected}
        if not result:
            record["error"] = error or window.status.text()
        else:
            record["result"] = result.to_dict()
        window.grab().save(str(output.with_suffix(".png")))
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        window.editor.document().setModified(False)
        window.close()
        app.exit(2 if record["error"] else 0)

    def poll():
        if started and not window.worker:
            finish()

    window._smoke_timer = QTimer(window)
    window._smoke_timer.timeout.connect(poll)
    window._smoke_timer.start(50)
    QTimer.singleShot(200, start)
    QTimer.singleShot(deadline * 1000, lambda: finish("GUI smoke test timed out"))
