import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from ocready.core.backend_errors import cuda_failure_detail
from ocready.core.containment import start_worker
from ocready.core.memory import stop_tree, tree_rss
from ocready.core.timeouts import PROCESS_TIMEOUT_SECONDS
from ocready.core.types import BudgetExceeded, Cancelled, OCRError

MAX_OUTPUT = 8_000_000


class WorkerFailed(OCRError):
    def __init__(self, message: str, *, exit_code: int, cuda_failure: bool):
        super().__init__(message)
        self.exit_code = exit_code
        self.cuda_failure = cuda_failure


@dataclass(frozen=True)
class ProcessResult:
    stdout: str
    stderr: str
    peak_rss: int
    elapsed: float
    containment: str = "rss-monitor"
    worker_limit: int = 0
    worker_peak: int = 0


def run_process(
    command: list[str], *, budget: int, cancel: threading.Event | None = None,
    timeout: float = PROCESS_TIMEOUT_SECONDS, env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> ProcessResult:
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled("Recognition cancelled.")
    started = time.monotonic()
    peak = tree_rss()
    if peak >= budget:
        raise BudgetExceeded("The application is already at this edition's RAM budget. Choose a larger edition or a smaller image.")
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            child, guard = start_worker(command, budget=budget, resident=peak, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        except (OSError, ValueError) as exc:
            raise OCRError(f"Could not start the OCR engine: {exc}") from exc
        try:
            while True:
                peak = max(peak, tree_rss())
                guard.sample()
                if guard.oom:
                    raise BudgetExceeded("The operating system stopped the OCR worker at its memory allowance. Try a smaller crop or a larger edition.")
                if cancel.is_set():
                    raise Cancelled("Recognition cancelled.")
                if peak >= budget:
                    raise BudgetExceeded(f"Recognition stopped at {peak / 1_000_000:.0f} MB to protect the edition's {budget / 1_000_000:g} MB budget. Try a smaller crop or a larger edition.")
                if time.monotonic() - started > timeout:
                    raise OCRError("The OCR engine took too long. Try a smaller crop or another method.")
                if stdout.tell() > MAX_OUTPUT or stderr.tell() > MAX_OUTPUT:
                    raise OCRError("The OCR engine produced too much diagnostic output.")
                exit_code = guard.poll(child)
                if exit_code is not None:
                    break
                cancel.wait(0.04)
            stdout.seek(0)
            stderr.seek(0)
            output = stdout.read(MAX_OUTPUT).decode("utf-8", errors="replace")
            error = stderr.read(MAX_OUTPUT).decode("utf-8", errors="replace")
            guard.completed()
            if guard.oom:
                raise BudgetExceeded("The operating system stopped the OCR worker at its memory allowance. Try a smaller crop or a larger edition.")
            if exit_code:
                status = f"exit code {exit_code}"
                if os.name == "nt":
                    status += f" (0x{exit_code & 0xFFFFFFFF:08X})"
                detail = error.strip()[-1600:]
                gpu_detail = cuda_failure_detail(error)
                if gpu_detail and gpu_detail not in detail:
                    detail = gpu_detail + "\n" + detail[-1200:]
                raise WorkerFailed(f"OCR engine failed, {status}" + (f": {detail}" if detail else "."),
                                   exit_code=exit_code, cuda_failure=bool(gpu_detail))
            return ProcessResult(output, error, peak, time.monotonic() - started,
                                 guard.mode, guard.limit_bytes, guard.peak_bytes)
        finally:
            if child.poll() is None:
                stop_tree(child.pid)
            child.wait()
            guard.close()
            if child.stdin:
                child.stdin.close()
