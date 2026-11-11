import re
import threading
import time
from pathlib import Path

from ocready.core.editions import Edition
from ocready.core.memory import tree_rss
from ocready.core.models import ModelPack
from ocready.core.process import run_process
from ocready.core.timeouts import CUDA_PROBE_TIMEOUT_SECONDS, VISION_TIMEOUT_SECONDS
from ocready.core.types import BudgetExceeded, Cancelled, OCRError, OCRResult
from ocready.engines.vision_adapters import clean_llama_output, get_adapter, local_environment


def runner_env(runner: str) -> dict[str, str]:
    return local_environment(runner)


def has_cuda(runner: str, edition: Edition, cancel: threading.Event | None, adapter_id: str = "llama.cpp") -> bool:
    adapter = get_adapter(adapter_id)
    try:
        result = run_process(adapter.probe_command(runner), budget=edition.budget, timeout=CUDA_PROBE_TIMEOUT_SECONDS,
                             env=adapter.environment(runner), cancel=cancel)
        return adapter.probe_cuda(result.stdout, result.stderr)
    except (Cancelled, BudgetExceeded):
        raise
    except OCRError:
        return False


def command(pack: ModelPack, image: Path, *, cuda: bool) -> list[str]:
    return get_adapter(pack.adapter).command(pack, image, cuda)


def clean_output(output: str) -> str:
    return clean_llama_output(output)


def recognize(image: Path, edition: Edition, pack: ModelPack, *, language: str = "ara+eng",
              backend: str = "auto", cancel: threading.Event | None = None, progress=lambda _message: None) -> OCRResult:
    if backend not in {"auto", "cpu", "cuda"}:
        raise OCRError("Choose Auto, CPU, or CUDA for vision inference.")
    pack.validate()
    adapter = get_adapter(pack.adapter)
    if any(value not in pack.languages.split("+") for value in language.split("+")):
        raise OCRError(f"{pack.name} is configured for {pack.languages}. Choose a matching language, or use Fast/Precision OCR for Arabic + English.")
    allowed, detail = pack.admission(edition, tree_rss())
    if not allowed:
        raise OCRError(detail)
    started = time.monotonic()
    cuda_program = pack.cuda_runner or pack.runner
    cuda = bool(backend != "cpu" and has_cuda(cuda_program, edition, cancel, pack.adapter))
    note = "AI transcription can omit or invent text. It has no reliable word boxes; compare with offline OCR."
    if backend == "cuda" and not cuda:
        note += " CUDA was unavailable; used CPU."
    progress(f"Reading with {pack.name} · {'CUDA' if cuda else 'CPU'}…")
    try:
        process = run_process(command(pack, image, cuda=cuda), budget=edition.budget, cancel=cancel,
                              timeout=VISION_TIMEOUT_SECONDS, env=adapter.environment(cuda_program if cuda else pack.runner))
    except (Cancelled, BudgetExceeded):
        raise
    except OCRError as exc:
        # Retry only backend-initialization failures, never an arbitrary model/configuration error.
        if not cuda or not re.search(r"cuda|cublas|gpu.*memory|out of memory", str(exc), re.IGNORECASE):
            raise
        progress("CUDA could not initialize. Retrying on CPU…")
        process = run_process(command(pack, image, cuda=False), budget=edition.budget, cancel=cancel,
                              timeout=VISION_TIMEOUT_SECONDS, env=adapter.environment(pack.runner))
        cuda = False
        note += " CUDA failed to initialize; retried on CPU."
    read = adapter.decode(process.stdout, image, cuda)
    if read.note:
        note += " " + read.note
    return OCRResult(read.text, engine=f"vision:{pack.id}", language=language,
                     elapsed=time.monotonic() - started, peak_rss=process.peak_rss,
                     backend=read.backend, note=note, containment=process.containment,
                     worker_limit=process.worker_limit, worker_peak=process.worker_peak, geometry="none", runtime=adapter.id)
