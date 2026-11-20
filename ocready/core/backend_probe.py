"""Parse the pinned llama.cpp device listing, without GUI/runtime dependencies."""
import re


def llama_device_listing(stdout: str) -> tuple[str, ...] | None:
    """None means an unrecognized response; an empty tuple is a CPU-only runner.

    Only stdout's actual listing counts. Startup logs, CUDA library names and
    stderr error messages do not establish an available device. The memory
    suffix is the format emitted by the pinned b12255 native runner.
    """
    lines = stdout.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "Available devices:")
    except StopIteration:
        return None
    devices = []
    for line in lines[start + 1:]:
        match = re.fullmatch(r"\s*(CUDA[0-9]+):\s+(.{1,240})\s+\(([0-9]+) MiB, ([0-9]+) MiB free\)\s*", line)
        if match and int(match[3]) > 0:
            devices.append(f"{match[1]}: {match[2]}")
    return tuple(dict.fromkeys(devices))
