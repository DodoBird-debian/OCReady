import io
import math
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from ocready.core.editions import Edition
from ocready.core.types import OCRError

MAX_DECODE_PIXELS = 32_000_000
MAX_FILE_BYTES = 100_000_000


def load_image(source: str | Path | bytes, edition: Edition) -> Image.Image:
    if isinstance(source, bytes):
        if len(source) > MAX_FILE_BYTES:
            raise OCRError("This image file is too large. Open an image smaller than 100 MB.")
        handle = io.BytesIO(source)
    else:
        path = Path(source)
        if not path.is_file():
            raise OCRError("The selected image no longer exists.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise OCRError("This image file is too large. Open an image smaller than 100 MB.")
        handle = path
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(handle) as image:
                pixels = image.width * image.height
                # Reject before decoding. Even downscaling requires a full decoder buffer.
                decode_limit = min(MAX_DECODE_PIXELS, edition.max_pixels * 2)
                if pixels > decode_limit:
                    raise OCRError(f"This image has {pixels / 1_000_000:.1f} million pixels. "
                                   f"{edition.name} accepts up to {decode_limit / 1_000_000:g} million; crop it first or choose a larger edition.")
                image = ImageOps.exif_transpose(image)
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    result = Image.new("RGB", rgba.size, "white")
                    result.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    result = image.convert("RGB")
        return fit_image(result, edition)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise OCRError("This file cannot be read as a safe image. Try PNG, JPEG, WebP, BMP, or TIFF.") from exc


def fit_image(image: Image.Image, edition: Edition) -> Image.Image:
    ratio = min(1.0, edition.max_edge / max(image.size),
                math.sqrt(edition.max_pixels / (image.width * image.height)))
    if ratio < 1:
        return image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                            Image.Resampling.LANCZOS)
    return image
