"""Compare lossless PNG and direct-pixel clipboard conversion on owned data."""
import argparse
import importlib.metadata
import json
import random
import statistics
import time
from pathlib import Path

from PIL import ImageChops
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from ocready.core.editions import EDITIONS
from ocready.core.images import load_image
from ocready.ui.images import qimage_to_source
from scripts.provenance import require_unchanged, source_record

ROOT = Path(__file__).resolve().parents[1]


def png_read(image, edition):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Reference PNG conversion failed")
    return load_image(bytes(buffer.data()), edition)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "test-output/clipboard-conversion.json")
    parser.add_argument("--repeats", type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    source = source_record(ROOT)
    report = {"source": source, "scope": "In-process pixel conversion; excludes OS clipboard transfer, OCR and packaged memory certification",
              "seed": 42, "repeats": args.repeats,
              "dependencies": {key: importlib.metadata.version(key) for key in ("Pillow", "PySide6-Essentials")}, "cases": []}
    for edition_id, size, alpha in [("pocket", (2000, 1000), False), ("everyday", (3200, 2500), False), ("pocket", (17, 19), True)]:
        channels = 4 if alpha else 3
        data = random.Random(42).randbytes(size[0] * size[1] * channels)
        image = QImage(data, *size, size[0] * channels,
                       QImage.Format.Format_RGBA8888 if alpha else QImage.Format.Format_RGB888).copy()
        times = {"png": [], "direct": []}
        for iteration in range(args.repeats):
            outputs = {}
            # Alternate order so every direct run is not systematically warm.
            methods = [("png", png_read), ("direct", qimage_to_source)]
            for label, method in methods if iteration % 2 == 0 else reversed(methods):
                start = time.perf_counter()
                outputs[label] = method(image, EDITIONS[edition_id])
                times[label].append(time.perf_counter() - start)
            if ImageChops.difference(outputs["png"], outputs["direct"]).getbbox() is not None:
                raise RuntimeError("Direct conversion changed the reference RGB pixels")
            for output in outputs.values():
                output.close()
        report["cases"].append({"edition": edition_id, "size": size, "alpha": alpha, "identical_rgb": True,
                                 "seconds": times, "median_seconds": {label: statistics.median(values) for label, values in times.items()}})
    require_unchanged(ROOT, source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": source, "medians": [row["median_seconds"] for row in report["cases"]]}))


if __name__ == "__main__":
    main()
