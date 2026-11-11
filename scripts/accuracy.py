"""Generate synthetic bilingual fixtures and measure transcription edit errors."""
import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

from PIL import Image

from ocready.core.editions import EDITIONS
from ocready.core.images import load_image
from ocready.core.models import load_pack
from ocready.core.pipeline import Request, recognize_image
from ocready.core.preprocess import Recipe
from scripts.provenance import file_sha256, source_record

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "assets" / "accuracy" / "manifest.json"

# Original test text, not scraped documents. Every case is scored separately.
ENGLISH = ["Your screenshots are ready to copy.", "Order 12345 costs 25.00 USD.", "Keep punctuation, numbers, and paragraphs."]
ARABIC = ["مرحبا بالعالم", "اللغة العربية واللغة الإنجليزية", "هذا النص جاهز للنسخ"]
CASES = [
    ("english-ui", "eng", "DejaVu Sans", 36, ENGLISH, {}),
    ("arabic-ui", "ara", "Noto Sans Arabic", 36, ARABIC, {}),
    ("bilingual-ui", "ara+eng", "DejaVu Sans", 36, [ENGLISH[0], *ARABIC[:2]], {}),
    ("arabic-naskh", "ara", "Noto Naskh Arabic", 42, ARABIC, {}),
    ("arabic-kufi", "ara", "Noto Kufi Arabic", 36, ARABIC, {}),
    ("arabic-diacritics", "ara", "Noto Naskh Arabic", 42,
     ["مَرْحَبًا بِالْعَالَمِ", "اللُّغَةُ الْعَرَبِيَّةُ", "نَصٌّ جَاهِزٌ لِلنَّسْخِ"], {}),
    ("mixed-digits", "ara+eng", "DejaVu Sans", 36,
     ["رقم الطلب OCReady 123", "الإجمالي ٢٥٠٠ دينار", "Contact: user@example.com"], {}),
    ("small-arabic", "ara", "Noto Sans Arabic", 18, ARABIC, {"scale": 2}),
    ("dark-bilingual", "ara+eng", "DejaVu Sans", 36, [ENGLISH[0], *ARABIC[:2]], {"invert": True}),
    ("low-contrast", "ara+eng", "DejaVu Sans", 36, [ENGLISH[0], *ARABIC[:2]], {"autocontrast": True}),
    ("rotated-bilingual", "ara+eng", "DejaVu Sans", 36, [ENGLISH[0], *ARABIC[:2]], {"rotation": 270}),
]


def normalized(text: str) -> str:
    # Ignore segmentation whitespace, preserving Arabic marks, digits and punctuation.
    return " ".join(unicodedata.normalize("NFC", text).split())


def edit_distance(reference, hypothesis) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def error_metrics(reference: str, hypothesis: str) -> dict:
    reference, hypothesis = normalized(reference), normalized(hypothesis)
    characters = len(reference)
    words = len(reference.split())
    char_errors = edit_distance(reference, hypothesis)
    word_errors = edit_distance(reference.split(), hypothesis.split())
    return {"character_errors": char_errors, "reference_characters": characters,
            "word_errors": word_errors, "reference_words": words,
            "cer": char_errors / max(1, characters), "wer": word_errors / max(1, words)}


def generate(manifest: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    available = set(QFontDatabase.families())
    missing = {case[2] for case in CASES} - available
    if missing:
        raise ValueError("Install the fixture fonts before regenerating: " + ", ".join(sorted(missing)))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for case_id, language, family, pixels, lines, recipe in CASES:
        image = QImage(1200, 320, QImage.Format.Format_RGB32)
        dark, low = case_id == "dark-bilingual", case_id == "low-contrast"
        image.fill(QColor("#181d26" if dark else "#eeeeee" if low else "#ffffff"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(QColor("#e3e6ec" if dark else "#ababab" if low else "#172238"))
        font = QFont(family)
        font.setPixelSize(pixels)
        painter.setFont(font)
        for index, line in enumerate(lines):
            first = next((unicodedata.bidirectional(c) for c in line if unicodedata.bidirectional(c) in {"L", "R", "AL"}), "L")
            alignment = Qt.AlignmentFlag.AlignRight if first in {"R", "AL"} else Qt.AlignmentFlag.AlignLeft
            painter.drawText(QRect(55, 35 + index * 85, 1090, 70), alignment | Qt.AlignmentFlag.AlignVCenter, line)
        painter.end()
        path = manifest.parent / f"{case_id}.png"
        if not image.save(str(path)):
            raise OSError(f"Could not save {path}")
        if case_id == "rotated-bilingual":
            with Image.open(path) as source:
                rotated = source.transpose(Image.Transpose.ROTATE_270)
            rotated.save(path)
        records.append({"id": case_id, "language": language, "font_family": family, "font_pixels": pixels,
                        "image": path.name, "image_sha256": file_sha256(path), "expected": "\n".join(lines), "recipe": recipe})
    manifest.write_text(json.dumps({"schema": 1, "description": "Original synthetic text; Qt-rendered Arabic/English accuracy cases, not a real-world accuracy certification.",
                                    "normalization": "NFC and collapsed whitespace only; diacritics/digits/punctuation are preserved",
                                    "cases": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(records)} fixtures in {manifest.parent}")
    del app


def evaluate(args) -> int:
    corpus = json.loads(args.manifest.read_text(encoding="utf-8"))
    edition = EDITIONS[args.edition]
    methods = args.methods.split(",")
    if not set(methods) <= {"fast", "best", "vision"} or ("vision" in methods and not args.model_pack):
        raise ValueError("Choose fast,best,vision and supply --model-pack for vision.")
    if "best" in methods and not edition.best_data:
        raise ValueError("Precision evaluation requires Everyday or Studio.")
    pack = load_pack(args.model_pack) if args.model_pack else None
    source = source_record(ROOT)
    rows = []
    for case in corpus["cases"]:
        path = args.manifest.parent / case["image"]
        if file_sha256(path) != case["image_sha256"]:
            raise ValueError(f"Fixture changed without updating its reference: {case['id']}")
        for method in methods:
            row = {"case": case["id"], "language": case["language"], "method": method}
            if method == "vision" and not set(case["language"].split("+")) <= set(pack.languages.split("+")):
                rows.append({**row, "status": "skipped", "reason": "Language unsupported by this pack"})
                continue
            try:
                image = load_image(path, edition)
                result, _ = recognize_image(image, Request(edition, case["language"], "vision" if method == "vision" else f"tesseract-{method}",
                                                           args.layout, Recipe(**case["recipe"]), args.compare,
                                                           model_pack=pack, backend=args.backend))
                metrics = error_metrics(case["expected"], result.text)
                rows.append({**row, "status": "ok", "expected": case["expected"], "actual": result.text,
                             "elapsed": result.elapsed, "engine": result.engine, "backend": result.backend, **metrics})
                print(f"{case['id']:22} {method:6} CER {metrics['cer']:.1%} · WER {metrics['wer']:.1%}", flush=True)
            except Exception as exc:
                rows.append({**row, "status": "error", "error": str(exc)})
                print(f"{case['id']:22} {method:6} ERROR {exc}", flush=True)
    summaries = {}
    for method in methods:
        completed = [row for row in rows if row["method"] == method and row["status"] == "ok"]
        chars = sum(row["reference_characters"] for row in completed)
        words = sum(row["reference_words"] for row in completed)
        summaries[method] = {"completed": len(completed), "cer": sum(row["character_errors"] for row in completed) / chars if chars else None,
                             "wer": sum(row["word_errors"] for row in completed) / words if words else None,
                             "skipped": sum(row["method"] == method and row["status"] == "skipped" for row in rows),
                             "errors": sum(row["method"] == method and row["status"] == "error" for row in rows)}
    report = {"source": source, "sources_changed_during_run": source_record(ROOT) != source,
              "platform": sys.platform,
              "corpus_sha256": file_sha256(args.manifest), "edition": edition.id,
              "normalization": corpus["normalization"], "layout": args.layout, "compare": args.compare,
              "summaries": summaries, "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 2 if (not any(row["status"] == "ok" for row in rows)
                 or any(row["status"] == "error" for row in rows) or report["sources_changed_during_run"]) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "evaluate"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=ROOT / "test-output" / "accuracy.json")
    parser.add_argument("--edition", choices=EDITIONS, default="everyday")
    parser.add_argument("--methods", default="fast,best")
    parser.add_argument("--layout", choices=("auto", "block", "sparse"), default="sparse")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--model-pack", type=Path)
    parser.add_argument("--backend", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    try:
        if args.mode == "generate":
            generate(args.manifest)
            return 0
        return evaluate(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Accuracy evaluation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
