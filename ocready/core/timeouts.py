"""Engine attempt limits and bounded diagnostic envelopes around real jobs."""

PROCESS_TIMEOUT_SECONDS = 120
VISION_TIMEOUT_SECONDS = 300
CUDA_PROBE_TIMEOUT_SECONDS = 20
GUI_GRACE_SECONDS = 30
STARTUP_GRACE_SECONDS = 120


def recognition_timeout_seconds(method: str, *, backend: str = "auto", compare: bool = False) -> int:
    kind = method.split(":", 1)[0]
    attempts = 1 if backend == "cpu" else 2
    if kind == "vision":
        return attempts * VISION_TIMEOUT_SECONDS + (CUDA_PROBE_TIMEOUT_SECONDS if backend != "cpu" else 0)
    if kind == "neural":
        return attempts * PROCESS_TIMEOUT_SECONDS
    return PROCESS_TIMEOUT_SECONDS * (2 if compare else 1)


def gui_workload_timeout_seconds(method: str, *, backend: str = "auto", compare: bool = False, loops: int = 1) -> int:
    return GUI_GRACE_SECONDS + max(1, loops) * recognition_timeout_seconds(method, backend=backend, compare=compare)


def observed_workload_timeout_seconds(method: str, *, backend: str = "auto", loops: int = 1) -> int:
    return STARTUP_GRACE_SECONDS + gui_workload_timeout_seconds(method, backend=backend, loops=loops)
