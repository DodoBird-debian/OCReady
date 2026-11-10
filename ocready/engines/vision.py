import os
import re
import threading
import time
from pathlib import Path

from ocready.core.editions import Edition
from ocready.core.memory import tree_rss
from ocready.core.models import ModelPack
from ocready.core.process import run_process
from ocready.core.types import BudgetExceeded, Cancelled, OCRError, OCRResult


def runner_env(runner: str) -> dict[str, str]:
    env = os.environ.copy()
    directory = str(Path(runner).expanduser().resolve().parent)
    if os.name == "nt":
        env["PATH"] = directory + os.pathsep + env.get("PATH", "")
    else:
        env["LD_LIBRARY_PATH"] = directory + os.pathsep + str(Path(directory).parent / "lib")
    return env


def has_cuda(runner: str, edition: Edition, cancel: threading.Event | None) -> bool:
    try:
        result = run_process([runner, "--list-devices"], budget=edition.budget, timeout=20,
                             env=runner_env(runner), cancel=cancel)
        return bool(re.search(r"CUDA\d|CUDA\s*:", result.stdout + result.stderr, re.IGNORECASE))
    except (Cancelled, BudgetExceeded):
        raise
    except OCRError:
        return False


def command(pack: ModelPack, image: Path, *, cuda: bool) -> list[str]:
    runner = (pack.cuda_runner or pack.runner) if cuda else pack.runner
    args = [str(Path(runner).expanduser()), "-m", str(Path(pack.model).expanduser()),
            "--mmproj", str(Path(pack.projector).expanduser()), "--image", str(image.resolve()),
            "-p", pack.prompt, "-n", str(pack.tokens), "--temp", "0", "--seed", "1",
            "-c", "4096", "-b", "256", "-ub", "128", "-t", str(min(8, os.cpu_count() or 2)),
            "--image-max-tokens", "1024", "--no-warmup", "--log-colors", "off", "-ngl", "99" if cuda else "0"]
    if not cuda:
        args.append("--no-mmproj-offload")
    return args


def clean_output(output: str) -> str:
    # Only strip known terminal/template artifacts, never arbitrary text lines.
    output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output).strip()
    for token in ("<|im_end|>", "<|endoftext|>", "<|eot_id|>"):
        output = output.removesuffix(token).rstrip()
    return output


def recognize(image: Path, edition: Edition, pack: ModelPack, *, language: str = "ara+eng",
              backend: str = "auto", cancel: threading.Event | None = None, progress=lambda _message: None) -> OCRResult:
    if backend not in {"auto", "cpu", "cuda"}:
        raise OCRError("Choose Auto, CPU, or CUDA for vision inference.")
    pack.validate()
    if any(value not in pack.languages.split("+") for value in language.split("+")):
        raise OCRError(f"{pack.name} is configured for {pack.languages}. Choose a matching language, or use Fast/Precision OCR for Arabic + English.")
    allowed, detail = pack.admission(edition, tree_rss())
    if not allowed:
        raise OCRError(detail)
    started = time.monotonic()
    cuda_program = pack.cuda_runner or pack.runner
    cuda = bool(backend != "cpu" and has_cuda(cuda_program, edition, cancel))
    note = "AI transcription can omit or invent text. It has no reliable word boxes; compare with offline OCR."
    if backend == "cuda" and not cuda:
        note += " CUDA was unavailable; used CPU."
    progress(f"Reading with {pack.name} · {'CUDA' if cuda else 'CPU'}…")
    try:
        process = run_process(command(pack, image, cuda=cuda), budget=edition.budget, cancel=cancel,
                              timeout=300, env=runner_env(cuda_program if cuda else pack.runner))
    except (Cancelled, BudgetExceeded):
        raise
    except OCRError as exc:
        # Retry only backend-initialization failures, never an arbitrary model/configuration error.
        if not cuda or not re.search(r"cuda|cublas|gpu.*memory|out of memory", str(exc), re.IGNORECASE):
            raise
        progress("CUDA could not initialize. Retrying on CPU…")
        process = run_process(command(pack, image, cuda=False), budget=edition.budget, cancel=cancel,
                              timeout=300, env=runner_env(pack.runner))
        cuda = False
        note += " CUDA failed to initialize; retried on CPU."
    return OCRResult(clean_output(process.stdout), engine=f"vision:{pack.id}", language=language,
                     elapsed=time.monotonic() - started, peak_rss=process.peak_rss,
                     backend="CUDA" if cuda else "CPU", note=note)
