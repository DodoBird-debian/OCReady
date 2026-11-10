import argparse
import json
import sys
from pathlib import Path

from ocready import __version__
from ocready.core.editions import EDITIONS, edition_for
from ocready.core.paths import build_profile, runtime_root
from ocready.core.types import OCRError


def diagnostics() -> dict:
    from ocready.engines.tesseract import data_dir, executable, readiness
    return {
        "version": __version__, "platform": sys.platform,
        "runtime": str(runtime_root()), "tesseract": str(executable() or "missing"),
        "fast_data": str(data_dir("fast") or "missing"),
        "best_data": str(data_dir("best") or "missing"),
        "ready": readiness()[0], "status": readiness()[1],
        "memory_policy": "process-tree RSS sampled every 40 ms; not an OS-enforced hard ceiling",
        "editions": {k: {"budget_bytes": v.budget, "max_pixels": v.max_pixels} for k, v in EDITIONS.items()},
    }


def main(argv: list[str] | None = None) -> int:
    profile = build_profile()
    parser = argparse.ArgumentParser(description="OCReady — local Arabic + English OCR")
    parser.add_argument("image", nargs="?", help="Image to open, or recognize with --text / --json")
    parser.add_argument("--version", action="version", version=f"OCReady {__version__}")
    parser.add_argument("--edition", choices=profile["available_editions"], default=profile["edition"])
    parser.add_argument("--language", choices=("ara+eng", "ara", "eng"), default="ara+eng")
    parser.add_argument("--method", choices=("tesseract-fast", "tesseract-best", "vision"), default="tesseract-fast")
    parser.add_argument("--model-pack", type=Path, help="Local vision model JSON manifest")
    parser.add_argument("--backend", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--layout", choices=("auto", "block", "sparse"), default="auto")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Recognize and emit JSON without opening a window")
    output.add_argument("--text", action="store_true", help="Recognize and emit plain text without opening a window")
    parser.add_argument("--output", type=Path, help="Write headless output to a UTF-8 file")
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--grayscale", action="store_true")
    parser.add_argument("--autocontrast", action="store_true")
    parser.add_argument("--threshold", type=int, choices=range(256), metavar="0..255")
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--compare", action="store_true", help="Compare two layouts sequentially")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--ui-smoke-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.method not in profile["methods"] and (args.text or args.json):
            raise OCRError("This OCR method is not included in this build.")
        if args.diagnostics:
            encoded = json.dumps(diagnostics(), ensure_ascii=False, indent=2)
        elif args.json or args.text:
            if not args.image:
                parser.error("an image is required for headless recognition")
            from ocready.core.images import load_image
            from ocready.core.pipeline import Request, recognize_image
            from ocready.core.preprocess import Recipe
            edition = edition_for(args.edition)
            source = load_image(args.image, edition)
            recipe = Recipe(invert=args.invert, grayscale=args.grayscale, autocontrast=args.autocontrast,
                            threshold=args.threshold, rotation=args.rotate)
            from ocready.core.models import load_pack
            pack = load_pack(args.model_pack) if args.model_pack else None
            result, _ = recognize_image(source, Request(edition, args.language, args.method, args.layout,
                                                        recipe, args.compare, pack, args.backend))
            encoded = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) if args.json else result.text
        else:
            from ocready.ui.app import run
            return run(args.image, args.edition, smoke_output=args.ui_smoke_output)
        if args.output:
            args.output.write_text(encoded + "\n", encoding="utf-8")
        else:
            # Windows console defaults must not corrupt Arabic in headless mode.
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(encoded)
        return 0
    except (OCRError, OSError, ValueError) as exc:
        print(f"OCReady: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
