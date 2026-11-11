from collections.abc import Iterable
from pathlib import Path

from ocready.core.editions import Edition


def local_engine_admission(edition: Edition, assets: Iterable[str], memory_mb: int,
                           resident_bytes: int, max_pixels: int, max_edge: int) -> tuple[bool, str]:
    """Estimate a sequential local runner without treating weight size as RAM."""
    weights = sum(Path(path).stat().st_size for path in assets if Path(path).is_file())
    pixels = min(edition.max_pixels, max_pixels, max_edge ** 2)
    reserve = 16_000_000 + pixels * 24
    required = max(memory_mb * 1_000_000, weights + 128_000_000) + resident_bytes + reserve
    if required >= edition.budget:
        return False, f"This pack needs an estimated {required / 1_000_000:.0f} MB including the app. It exceeds {edition.name}'s budget."
    return True, f"Estimated {required / 1_000_000:.0f} MB total; runtime memory is monitored. This estimate is not certification."
