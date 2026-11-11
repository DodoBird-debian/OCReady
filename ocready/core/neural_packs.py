import dataclasses
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ocready.core.admission import local_engine_admission
from ocready.core.cuda_helpers import NEURAL_ADAPTER, cuda_helper
from ocready.core.editions import Edition
from ocready.core.paths import build_profile, config_root, runtime_root
from ocready.core.types import OCRError

ASSET_FIELDS = ("runner", "detector", "recognizer", "dictionary", "cuda_runner")
PACK_OPTIONS = ("name", "memory_mb", "max_pixels", "max_edge", "languages", "direction", "decode")


@dataclass(frozen=True)
class NeuralPack:
    id: str
    name: str
    runner: str
    detector: str
    recognizer: str
    dictionary: str
    cuda_runner: str = ""
    memory_mb: int = 300
    max_pixels: int = 2_000_000
    max_edge: int = 2400
    languages: str = "ara+eng"
    direction: str = "auto"
    decode: str = "visual"
    source: str = "User-provided local neural OCR models"
    license: str = "See the model licenses"
    bundled: bool = False

    def validate(self, *, require_cuda: bool = True) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", self.id) or not self.name.strip() or len(self.name) > 120:
            raise OCRError("Give the neural pack a short name and a valid letter/digit/underscore/hyphen ID.")
        if not 100 <= self.memory_mb <= 3800:
            raise OCRError("Set a runner memory estimate between 100 and 3800 MB.")
        if not 250_000 <= self.max_pixels <= 4_000_000 or not 512 <= self.max_edge <= 3000:
            raise OCRError("Neural input limits must be 0.25–4 million pixels and 512–3000 pixels per edge.")
        if self.languages not in {"ara+eng", "ara", "eng"} or self.direction not in {"auto", "rtl", "ltr"} or self.decode not in {"visual", "logical"}:
            raise OCRError("Choose supported languages, reading direction, and model text encoding.")
        for key in ASSET_FIELDS:
            value = getattr(self, key)
            if key == "cuda_runner" and (not require_cuda or not value):
                continue
            if not value or not Path(value).expanduser().is_file():
                raise OCRError(f"The neural {key} file does not exist. Import its manifest in Settings.")
        dictionary = Path(self.dictionary).expanduser()
        if dictionary.stat().st_size > 1_000_000:
            raise OCRError("The neural character dictionary is too large.")
        try:
            if not dictionary.read_text(encoding="utf-8").splitlines():
                raise ValueError("empty dictionary")
        except (UnicodeError, ValueError) as exc:
            raise OCRError("Choose a nonempty UTF-8 character dictionary.") from exc

    def admission(self, edition: Edition, resident_bytes: int = 150_000_000) -> tuple[bool, str]:
        if not edition.vision:
            return False, "This neural OCR runner is tested for Everyday and Studio. Pocket uses compact classical OCR."
        return local_engine_admission(edition, (self.detector, self.recognizer), self.memory_mb,
                                      resident_bytes, self.max_pixels, self.max_edge)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NeuralPack":
        if not isinstance(data, dict):
            raise OCRError("The neural manifest must contain a JSON object.")
        fields = {f.name: f for f in dataclasses.fields(cls)}
        try:
            pack = cls(**{key: value for key, value in data.items() if key in fields})
            for key in fields:
                expected = bool if key == "bundled" else int if key in {"memory_mb", "max_pixels", "max_edge"} else str
                if type(getattr(pack, key)) is not expected:
                    raise ValueError(f"invalid type for {key}")
            if not 250_000 <= pack.max_pixels <= 4_000_000 or not 512 <= pack.max_edge <= 3000:
                raise ValueError("image limits out of range")
            if pack.languages not in {"ara+eng", "ara", "eng"} or pack.direction not in {"auto", "rtl", "ltr"} or pack.decode not in {"visual", "logical"}:
                raise ValueError("unsupported language or text-order declaration")
            return pack
        except (TypeError, ValueError) as exc:
            raise OCRError(f"Invalid neural manifest: {exc}") from exc


def load_neural_pack(path: Path) -> NeuralPack:
    try:
        if path.stat().st_size > 100_000:
            raise OCRError("The neural manifest is too large.")
        values = NeuralPack.from_dict(json.loads(path.read_text(encoding="utf-8"))).to_dict()
        for key in ASSET_FIELDS:
            if values[key] and not Path(values[key]).is_absolute():
                values[key] = str((path.parent / values[key]).resolve())
        return NeuralPack.from_dict(values)
    except (OSError, ValueError) as exc:
        raise OCRError(f"Could not read the neural manifest: {exc}") from exc


def _user_packs() -> list[NeuralPack]:
    packs = []
    path = config_root() / "neural-models.json"
    try:
        if path.stat().st_size <= 1_000_000:
            records = json.loads(path.read_text(encoding="utf-8"))
            for data in records[:20] if isinstance(records, list) else []:
                try:
                    pack = NeuralPack.from_dict(data)
                    packs.append(pack)
                except OCRError:
                    continue
    except (OSError, ValueError):
        pass
    return packs


def load_neural_packs() -> list[NeuralPack]:
    packs = {}
    if "neural" in build_profile()["methods"]:
        for path in sorted((runtime_root() / "neural").glob("*/pack.json")):
            try:
                pack = dataclasses.replace(load_neural_pack(path), bundled=True)
                packs[pack.id] = pack
            except OCRError:
                continue
    for pack in _user_packs():
        if pack.bundled:
            if pack.id in packs:
                packs[pack.id] = dataclasses.replace(packs[pack.id], **{key: getattr(pack, key) for key in PACK_OPTIONS})
        else:
            packs[pack.id] = pack
    return [dataclasses.replace(pack, cuda_runner=helper) if pack.bundled and
            (helper := cuda_helper("neural", pack.id, NEURAL_ADAPTER)) else pack for pack in packs.values()]


def save_neural_packs(packs: list[NeuralPack]) -> None:
    path = config_root() / "neural-models.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    present = {pack.id for pack in packs}
    retained = [pack for pack in _user_packs() if pack.bundled and pack.id not in present]
    records = []
    for pack in [*retained, *packs]:
        record = pack.to_dict()
        if pack.bundled:
            record.update({key: "" for key in ASSET_FIELDS})
        records.append(record)
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
