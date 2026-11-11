"""Diagnostic path for testing the actual compiled native GUI without QtTest."""
import json
from pathlib import Path

from PySide6.QtCore import QTimer

from ocready.core.memory import tree_rss
from ocready.core.timeouts import gui_workload_timeout_seconds


def attach_smoke_run(app, window, image: str | None, output: Path) -> None:
    started = False
    deadline = gui_workload_timeout_seconds(str(window.method_combo.currentData()), backend=window.vision_backend,
                                           compare=window.compare_check.isChecked())

    def start():
        nonlocal started
        if image:
            window.open_path(image)
        else:
            window.load_example()
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
        output.parent.mkdir(parents=True, exist_ok=True)
        record = {"text": window.editor.toPlainText(), "words": len(window.canvas.words),
                  "linked": window.editor.linked, "rss": tree_rss(), "error": error, "deadline_seconds": deadline}
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
