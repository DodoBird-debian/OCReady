"""Render a shaped bilingual screenshot with Qt (no raster image generation)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication.instance() or QApplication([])
    image = QImage(1100, 720, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setPen(QColor("#26334b"))
    painter.setFont(QFont("DejaVu Sans", 30, QFont.Weight.Bold))
    painter.drawText(QRect(60, 50, 980, 65), Qt.AlignmentFlag.AlignLeft, "A little less typing.")
    painter.setFont(QFont("DejaVu Sans", 24))
    painter.drawText(QRect(60, 145, 980, 60), Qt.AlignmentFlag.AlignLeft, "Turn your screenshots into something useful.")
    painter.drawText(QRect(60, 220, 980, 60), Qt.AlignmentFlag.AlignLeft, "Select a word. Copy a sentence. Keep going.")
    painter.setPen(QColor("#225fbe"))
    painter.setFont(QFont("DejaVu Sans", 30))
    painter.drawText(QRect(60, 350, 980, 75), Qt.AlignmentFlag.AlignRight, "مرحبا بالعالم")
    painter.setPen(QColor("#26334b"))
    painter.setFont(QFont("DejaVu Sans", 25))
    painter.drawText(QRect(60, 450, 980, 75), Qt.AlignmentFlag.AlignRight, "اللغة العربية واللغة الإنجليزية")
    painter.setFont(QFont("DejaVu Sans", 22))
    painter.drawText(QRect(60, 580, 980, 70), Qt.AlignmentFlag.AlignLeft, "OCReady  /  Local. Private. Ready to copy.")
    painter.end()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assets/sample-bilingual.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target)):
        raise RuntimeError(f"Cannot save {target}")
    print(target)
    del app


if __name__ == "__main__":
    main()
