import json
import math
import re
import threading
from pathlib import Path

from PIL import Image

from ocready.core.editions import Edition
from ocready.core.memory import tree_rss
from ocready.core.neural_packs import NeuralPack
from ocready.core.process import run_process
from ocready.core.timeouts import PROCESS_TIMEOUT_SECONDS
from ocready.core.types import Box, BudgetExceeded, Cancelled, OCRError, OCRResult, Word
from ocready.engines.vision import runner_env


def parse_output(output: str, expected_size: tuple[int, int], *, pack: NeuralPack, language: str) -> OCRResult:
    try:
        data = json.loads(output)
        width, height = expected_size
        if (type(data) is not dict or data.get("schema") != 1 or data.get("width") != width or data.get("height") != height
                or data.get("backend") not in {"CPU", "CUDA"} or not isinstance(data.get("lines"), list)
                or len(data["lines"]) > 2000):
            raise ValueError("invalid dimensions, backend or line list")
        words, chunks, offset = [], [], 0
        for index, line in enumerate(data["lines"]):
            text, polygon, score = line["text"], line["polygon"], line["score"]
            if not isinstance(text, str) or len(text) > 20_000 or not isinstance(polygon, list) or len(polygon) != 4:
                raise ValueError("invalid line text or polygon")
            if not all(isinstance(point, list) and len(point) == 2 and
                       all(type(v) in (int, float) and math.isfinite(v) for v in point) for point in polygon):
                raise ValueError("invalid polygon coordinates")
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("invalid recognition score")
            text = text.strip()
            if not text:
                continue
            left = max(0, min(width, math.floor(min(point[0] for point in polygon))))
            top = max(0, min(height, math.floor(min(point[1] for point in polygon))))
            right = max(0, min(width, math.ceil(max(point[0] for point in polygon))))
            bottom = max(0, min(height, math.ceil(max(point[1] for point in polygon))))
            if right <= left or bottom <= top:
                raise ValueError("empty line region")
            if chunks:
                chunks.append("\n")
                offset += 1
            chunks.append(text)
            words.append(Word(text, Box(left, top, right - left, bottom - top), score * 100,
                              offset, offset + len(text), (1, 1, 1, index + 1)))
            offset += len(text)
        note = data.get("note", "")
        if not isinstance(note, str) or len(note) > 4000:
            raise ValueError("invalid note")
        return OCRResult("".join(chunks), words, engine=f"neural:{pack.id}", language=language,
                         backend=data["backend"], note=note, geometry="line")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise OCRError(f"The neural runner returned an invalid OCR response: {exc}") from exc


def recognize(image: Path, edition: Edition, pack: NeuralPack, *, language: str = "ara+eng",
              backend: str = "auto", cancel: threading.Event | None = None, progress=lambda _text: None) -> OCRResult:
    if backend not in {"auto", "cpu", "cuda"}:
        raise OCRError("Choose Auto, CPU or CUDA for neural OCR.")
    pack.validate()
    if not set(language.split("+")) <= set(pack.languages.split("+")):
        raise OCRError(f"{pack.name} is configured for {pack.languages}. Choose a matching language.")
    allowed, reason = pack.admission(edition, tree_rss())
    if not allowed:
        raise OCRError(reason)
    with Image.open(image) as source:
        size = source.size
    runner = pack.cuda_runner if backend != "cpu" and pack.cuda_runner else pack.runner
    def command(program: str, compute: str) -> list[str]:
        return [program, "--image", str(image.resolve()), "--detector", pack.detector,
                "--recognizer", pack.recognizer, "--dictionary", pack.dictionary,
                "--backend", compute, "--direction", pack.direction, "--decode", pack.decode]
    progress(f"Reading with {pack.name}…")
    try:
        process = run_process(command(runner, backend), budget=edition.budget, cancel=cancel,
                              timeout=PROCESS_TIMEOUT_SECONDS, env=runner_env(runner))
    except (Cancelled, BudgetExceeded):
        raise
    except OCRError as exc:
        if runner == pack.runner or not re.search(r"cuda|cudnn|cublas|gpu.*memory", str(exc), re.IGNORECASE):
            raise
        progress("CUDA could not initialize. Retrying neural OCR on CPU…")
        process = run_process(command(pack.runner, "cpu"), budget=edition.budget, cancel=cancel,
                              timeout=PROCESS_TIMEOUT_SECONDS, env=runner_env(pack.runner))
    result = parse_output(process.stdout, size, pack=pack, language=language)
    if not result.text:
        result.note = (result.note + " No text lines found. Try a tighter crop or another OCR method.").strip()
    result.elapsed, result.peak_rss = process.elapsed, process.peak_rss
    result.containment, result.worker_limit, result.worker_peak = process.containment, process.worker_limit, process.worker_peak
    return result
