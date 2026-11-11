import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from PIL import Image

from ocready.core.editions import Edition
from ocready.core.models import ModelPack
from ocready.core.neural_packs import NeuralPack
from ocready.core.preprocess import Recipe, preprocess
from ocready.core.types import Cancelled, OCRError, OCRResult
from ocready.engines import tesseract


@dataclass(frozen=True)
class Request:
    edition: Edition
    language: str = "ara+eng"
    method: str = "tesseract-fast"
    layout: str = "auto"
    recipe: Recipe = field(default_factory=Recipe)
    compare: bool = False
    model_pack: ModelPack | None = None
    backend: str = "auto"
    neural_pack: NeuralPack | None = None


def image_policy(edition: Edition, method: str, pack: ModelPack | NeuralPack | None = None) -> Edition:
    """Use identical input bounds for the displayed preview and engine image."""
    if not method.startswith(("vision", "neural")):
        return edition
    return replace(edition, max_pixels=min(edition.max_pixels, pack.max_pixels if pack else 1_000_000),
                   max_edge=min(edition.max_edge, pack.max_edge if pack else 1600))


def recognize_image(source: Image.Image, request: Request, *, cancel: threading.Event | None = None,
                    progress: Callable[[str], None] = lambda _: None) -> tuple[OCRResult, list[OCRResult]]:
    cancel = cancel or threading.Event()
    started = time.monotonic()
    progress("Preparing image…")
    pack = request.neural_pack if request.method.startswith("neural") else request.model_pack
    processed = preprocess(source, request.recipe, image_policy(request.edition, request.method, pack))
    results = []
    with tempfile.TemporaryDirectory(prefix="ocready-ocr-") as directory:
        image_path = Path(directory) / "image.png"
        processed.save(image_path)
        del processed
        if cancel.is_set():
            raise Cancelled("Recognition cancelled.")
        progress("Reading Arabic and English…")
        if request.method.startswith("vision"):
            from ocready.engines import vision
            if not request.model_pack:
                raise OCRError("Choose a local vision model in Settings before using AI transcription.")
            result = vision.recognize(image_path, request.edition, request.model_pack, language=request.language,
                                      backend=request.backend, cancel=cancel, progress=progress)
        elif request.method.startswith("neural"):
            from ocready.engines import neural
            if not request.neural_pack:
                raise OCRError("Choose a local neural OCR pack before recognizing text.")
            result = neural.recognize(image_path, request.edition, request.neural_pack, language=request.language,
                                      backend=request.backend, cancel=cancel, progress=progress)
        elif request.method in {"tesseract-fast", "tesseract-best"}:
            quality = "best" if request.method == "tesseract-best" else "fast"
            result = tesseract.recognize(image_path, request.edition, language=request.language,
                                         layout=request.layout, quality=quality, cancel=cancel)
        else:
            raise OCRError("The selected OCR method is not supported.")
        result.recipe = request.recipe.label
        results.append(result)
        if request.compare and request.method.startswith("tesseract"):
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
