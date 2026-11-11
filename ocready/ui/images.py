"""Bounded Qt-to-Pillow transfers for screenshot paste/capture workflows."""
from PIL import Image
from PySide6.QtGui import QImage

from ocready.core.editions import Edition
from ocready.core.images import MAX_DECODE_PIXELS, fit_image
from ocready.core.types import OCRError


def qimage_to_source(image: QImage, edition: Edition) -> Image.Image:
    if image.isNull():
        raise OCRError("No image is available to paste.")
    if image.width() * image.height() > min(MAX_DECODE_PIXELS, edition.max_pixels * 2):
        raise OCRError(f"This clipboard image is too large for {edition.name}. Capture a smaller region or choose a larger edition.")
    # Normalize channel order, palette and premultiplied alpha once. The PIL
    # view borrows only while `converted` is alive; the returned RGB owns data.
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if converted.isNull():
        raise OCRError("Not enough memory to paste this image. Try a smaller capture.")
    rgba = Image.frombuffer("RGBA", (converted.width(), converted.height()), converted.constBits(),
                            "raw", "RGBA", converted.bytesPerLine(), 1)
    # constBits exports a view without a Qt owner. Attach that owner to the
    # borrowing PIL image so optimized/compiled local-variable lifetimes are
    # irrelevant. RGB conversion/paste below returns independent pixels.
    rgba._ocready_qimage_owner = converted
    if image.hasAlphaChannel():
        result = Image.new("RGB", rgba.size, "white")
        result.paste(rgba, mask=rgba.getchannel("A"))
    else:
        result = rgba.convert("RGB")
    return fit_image(result, edition)
