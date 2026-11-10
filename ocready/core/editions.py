from dataclasses import dataclass


@dataclass(frozen=True)
class Edition:
    id: str
    name: str
    budget: int
    max_pixels: int
    max_edge: int
    best_data: bool = False
    vision: bool = False

    @property
    def budget_label(self) -> str:
        return f"{self.budget // 1_000_000} MB" if self.budget < 1_000_000_000 else f"{self.budget // 1_000_000_000} GB"


EDITIONS = {
    "pocket": Edition("pocket", "Pocket", 350_000_000, 2_000_000, 3000),
    "everyday": Edition("everyday", "Everyday", 1_000_000_000, 8_000_000, 6000, best_data=True),
    "studio": Edition("studio", "Studio", 4_000_000_000, 16_000_000, 8000, best_data=True, vision=True),
}


def edition_for(name: str) -> Edition:
    try:
        return EDITIONS[name]
    except KeyError:
        raise ValueError(f"Unknown edition: {name}") from None
