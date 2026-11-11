from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if min(self.x, self.y, self.width, self.height) < 0:
            raise ValueError("A text box cannot have negative coordinates or dimensions.")

    def intersects(self, other: "Box") -> bool:
        return (
            self.x < other.x + other.width and other.x < self.x + self.width
            and self.y < other.y + other.height and other.y < self.y + self.height
        )


@dataclass(frozen=True)
class Word:
    text: str
    box: Box
    confidence: float | None
    start: int
    end: int
    line: tuple[int, ...] = ()


@dataclass
class OCRResult:
    text: str
    words: list[Word] = field(default_factory=list)
    engine: str = "tesseract-fast"
    language: str = "ara+eng"
    elapsed: float = 0.0
    peak_rss: int = 0
    backend: str = "CPU"
    recipe: str = "Original"
    note: str = ""
    containment: str = "rss-monitor"
    worker_limit: int = 0
    worker_peak: int = 0
    layout: str = ""

    @property
    def confidence(self) -> float | None:
        values = [w.confidence for w in self.words if w.confidence is not None]
        return sum(values) / len(values) if values else None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "confidence": self.confidence}


class OCRError(Exception):
    """A recoverable error that can be shown directly in the UI."""


class Cancelled(OCRError):
    pass


class BudgetExceeded(OCRError):
    pass
