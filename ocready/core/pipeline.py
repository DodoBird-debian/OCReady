import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from ocready.core.editions import Edition
from ocready.core.preprocess import Recipe, preprocess
from ocready.core.types import Cancelled, OCRResult
from ocready.engines import tesseract


@dataclass(frozen=True)
class Request:
    edition: Edition
    language: str = "ara+eng"
    method: str = "tesseract-fast"
    layout: str = "auto"
    recipe: Recipe = field(default_factory=Recipe)
    compare: bool = False


def recognize_image(source: Image.Image, request: Request, *, cancel: threading.Event | None = None,
                    progress: Callable[[str], None] = lambda _: None) -> tuple[OCRResult, list[OCRResult]]:
    cancel = cancel or threading.Event()
    started = time.monotonic()
    progress("Preparing image…")
    processed = preprocess(source, request.recipe, request.edition)
    results = []
    with tempfile.TemporaryDirectory(prefix="ocready-ocr-") as directory:
        image_path = Path(directory) / "image.png"
        processed.save(image_path)
        del processed
        if cancel.is_set():
            raise Cancelled("Recognition cancelled.")
        progress("Reading Arabic and English…")
        quality = "best" if request.method == "tesseract-best" else "fast"
        result = tesseract.recognize(image_path, request.edition, language=request.language,
                                     layout=request.layout, quality=quality, cancel=cancel)
        result.recipe = request.recipe.label
        results.append(result)
        if request.compare:
            progress("Comparing screenshot layout…")
            alternative_layout = "sparse" if request.layout != "sparse" else "block"
            alternative = tesseract.recognize(image_path, request.edition, language=request.language,
                                               layout=alternative_layout, quality=quality, cancel=cancel)
            alternative.recipe = request.recipe.label + f" · {alternative_layout} layout"
            results.append(alternative)
    # Compare only equivalent Tesseract scores; never equate them with VLM confidence.
    best = max(results, key=lambda r: (bool(r.text), r.confidence or 0))
    best.elapsed = time.monotonic() - started
    best.peak_rss = max(r.peak_rss for r in results)
    return best, results
