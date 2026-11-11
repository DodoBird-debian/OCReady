import pytest
from PIL import ImageChops
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from ocready.core.editions import EDITIONS
from ocready.core.images import load_image
from ocready.core.types import OCRError
from ocready.ui.images import qimage_to_source


@pytest.mark.parametrize("format", [QImage.Format.Format_RGB888, QImage.Format.Format_RGBA8888,
    QImage.Format.Format_ARGB32_Premultiplied, QImage.Format.Format_Grayscale8, QImage.Format.Format_Indexed8])
def test_direct_clipboard_transfer_matches_lossless_reference_and_owns_pixels(format):
    # Odd RGB widths exercise row padding; alpha/palettes cover screenshot and
    # transparent application clipboard providers on both native platforms.
    image = QImage(13, 7, format)
    if format == QImage.Format.Format_Indexed8:
        image.setColorTable([QColor(12, 34, 56).rgba(), QColor(255, 0, 0, 128).rgba(), QColor(0, 0, 0, 0).rgba()])
        for y in range(image.height()):
            for x in range(image.width()):
                image.setPixel(x, y, (x + y) % 3)
    else:
        for y in range(image.height()):
            for x in range(image.width()):
                image.setPixelColor(x, y, QColor((x * 23) % 256, (y * 41) % 256, 79, (x * 37 + y * 17) % 256))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    expected = load_image(bytes(buffer.data()), EDITIONS["pocket"])
    actual = qimage_to_source(image, EDITIONS["pocket"])
    assert actual.mode == "RGB" and ImageChops.difference(actual, expected).getbbox() is None
    image.fill(QColor("green"))
    del image
    assert ImageChops.difference(actual, expected).getbbox() is None


def test_clipboard_transparency_flattens_on_white_and_admission_precedes_conversion():
    image = QImage(3, 1, QImage.Format.Format_RGBA8888)
    for x, alpha in enumerate((0, 128, 255)):
        image.setPixelColor(x, 0, QColor(255, 0, 0, alpha))
    result = qimage_to_source(image, EDITIONS["pocket"])
    assert [result.getpixel((x, 0)) for x in range(3)] == [(255, 255, 255), (255, 127, 127), (255, 0, 0)]
    with pytest.raises(OCRError, match="too large"):
        qimage_to_source(QImage(3000, 2000, QImage.Format.Format_Mono), EDITIONS["pocket"])
    with pytest.raises(OCRError, match="No image"):
        qimage_to_source(QImage(), EDITIONS["pocket"])


def test_direct_clipboard_transfer_retains_the_edition_processing_cap():
    image = QImage(2000, 2000, QImage.Format.Format_RGB888)
    image.fill(QColor("white"))
    result = qimage_to_source(image, EDITIONS["pocket"])
    assert result.width * result.height <= EDITIONS["pocket"].max_pixels
