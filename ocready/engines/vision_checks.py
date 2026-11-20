"""Explicit, bounded runner diagnostics. No weights or source images are loaded."""
import threading
from pathlib import Path

from ocready.core.editions import Edition
from ocready.core.memory import tree_rss
from ocready.core.models import ModelPack
from ocready.core.process import run_process
from ocready.core.timeouts import CUDA_PROBE_TIMEOUT_SECONDS
from ocready.core.types import Cancelled, OCRError
from ocready.engines.vision_adapters import get_adapter


def check_model_backends(pack: ModelPack, edition: Edition, *, cancel: threading.Event | None = None) -> dict:
    adapter = get_adapter(pack.adapter)
    try:
        pack.validate(require_cuda=False)
        assets_error = ""
    except (OCRError, OSError) as exc:
        assets_error = str(exc)[:600]
    admitted, admission = pack.admission(edition, tree_rss())
    checks = {}

    def check(value: str) -> dict:
        path = Path(value).expanduser().resolve()
        key = str(path)
        if key in checks:
            return checks[key]
        if not value or not path.is_file():
            report = {"status": "missing", "backends": [], "detail": "Runner file is unavailable."}
        else:
            try:
                result = run_process(adapter.probe_command(str(path)), budget=edition.budget,
                                     timeout=CUDA_PROBE_TIMEOUT_SECONDS, cancel=cancel,
                                     env=adapter.environment(str(path)))
                backends = adapter.probe_backends(result.stdout, result.stderr)
                report = {"status": "responding", "backends": list(backends),
                          "detail": "Runner responded; model inference has not been tested."}
            except Cancelled:
                raise
            except OCRError as exc:
                report = {"status": "failed", "backends": [], "detail": str(exc)[:600]}
        checks[key] = report
        return report

    cpu = check(pack.runner)
    cuda = check(pack.cuda_runner or pack.runner)
    cpu_available = "cpu" in cpu["backends"]
    cuda_detected = "cuda" in cuda["backends"]
    return {"id": pack.id, "name": pack.name, "adapter": pack.adapter, "chat_template": pack.chat_template,
            "assets_valid": not assets_error, "assets_error": assets_error,
            "admitted": admitted, "admission": admission, "cpu_runner": cpu, "cuda_runner": cuda,
            "cpu_available": cpu_available, "cuda_device_detected": cuda_detected,
            "can_attempt_inference": not assets_error and admitted and cpu_available,
            "automatic_backend": "CUDA" if cuda_detected and cpu_available else "CPU" if cpu_available else "unavailable",
            "inference_verified": False}
