import os
import shutil
import threading
from pathlib import Path

from ocready.core.editions import Edition
from ocready.core.paths import runtime_root
from ocready.core.process import run_process
from ocready.core.text import parse_tsv
from ocready.core.types import OCRError, OCRResult

LANGUAGES = {"ara+eng": "Arabic + English", "ara": "العربية · Arabic", "eng": "English"}
LAYOUTS = {"auto": (3, "Automatic page"), "block": (6, "Single text block"), "sparse": (11, "Screenshot / scattered text")}


def executable() -> Path | None:
    override = os.environ.get("OCREADY_TESSERACT")
    if override:
        return Path(override).expanduser()
    name = "tesseract.exe" if os.name == "nt" else "tesseract"
    bundled = runtime_root() / "bin" / name
    if bundled.is_file():
        return bundled
    found = shutil.which(name)
    return Path(found) if found else None


def data_dir(quality: str = "fast") -> Path | None:
    candidates = [runtime_root() / "tessdata" / quality]
    if quality == "fast":
        prefix = os.environ.get("TESSDATA_PREFIX")
        if prefix:
            candidates.append(Path(prefix))
        candidates += [Path("/usr/share/tesseract-ocr/5/tessdata"), Path("/usr/share/tessdata")]
    return next((p for p in candidates if p.is_dir() and (p / "eng.traineddata").is_file()), None)


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["OMP_THREAD_LIMIT"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    libs = runtime_root() / "lib"
    if libs.is_dir() and os.name != "nt":
        env["LD_LIBRARY_PATH"] = str(libs) + (os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    if os.name == "nt":
        env["PATH"] = str(runtime_root() / "bin") + os.pathsep + env.get("PATH", "")
    return env


def readiness(quality: str = "fast") -> tuple[bool, str]:
    if not executable():
        return False, "OCR runtime missing. Run scripts/prepare_runtime.py or install Tesseract."
    data = data_dir(quality)
    if not data or not (data / "ara.traineddata").is_file():
        return False, f"Arabic + English {quality} language data is not installed."
    return True, "Ready · offline Arabic + English"


def recognize(image: Path, edition: Edition, *, language: str = "ara+eng", layout: str = "auto",
              quality: str = "fast", cancel: threading.Event | None = None) -> OCRResult:
    if language not in LANGUAGES or layout not in LAYOUTS or quality not in {"fast", "best"}:
        raise OCRError("Choose a supported language, layout, and OCR method.")
    if quality == "best" and not edition.best_data:
        raise OCRError("Best language data needs Everyday or Studio. Pocket uses the smaller fast models.")
    ready, message = readiness(quality)
    if not ready:
        raise OCRError(message)
    program, data = executable(), data_dir(quality)
    assert program and data
    process = run_process([str(program), str(image.resolve()), "stdout", "--tessdata-dir", str(data),
                           "-l", language, "--oem", "1", "--psm", str(LAYOUTS[layout][0]),
                           "-c", "tessedit_create_tsv=1"],
                          budget=edition.budget, cancel=cancel, env=runtime_env())
    result = parse_tsv(process.stdout, engine=f"tesseract-{quality}", language=language)
    result.elapsed, result.peak_rss = process.elapsed, process.peak_rss
    result.containment, result.worker_limit, result.worker_peak = process.containment, process.worker_limit, process.worker_peak
    if not result.text:
        result.note = "No text found. Try a tighter crop, invert a dark background, or change the page layout."
    return result
