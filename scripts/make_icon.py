"""Render OCReady's owned vector mark into portable PNG and Windows ICO assets."""
import io
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ROOT / "assets/ocready.svg"))
    if not renderer.isValid():
        raise RuntimeError("The application vector icon is invalid.")
    raster = QImage(1024, 1024, QImage.Format.Format_ARGB32_Premultiplied)
    raster.fill(Qt.GlobalColor.transparent)
    painter = QPainter(raster)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not raster.save(buffer, "PNG"):
        raise RuntimeError("Could not render the application icon.")
    with Image.open(io.BytesIO(bytes(buffer.data()))) as image:
        image = image.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
        image.save(ROOT / "assets/ocready.png")
        image.save(ROOT / "assets/ocready.ico", format="ICO",
                   sizes=[(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    buffer.close()
    app.processEvents()
    print("Rendered assets/ocready.png and assets/ocready.ico from assets/ocready.svg")


if __name__ == "__main__":
    main()
