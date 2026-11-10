"""Execute a compiled onefile artifact without its source-runtime override."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    directory = Path(sys.argv[1]).resolve()
    binary = next(p for p in directory.glob("OCReady-*") if p.is_file() and not p.name.endswith(".sha256"))
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items()
           if key not in {"OCREADY_RUNTIME", "OCREADY_TESSERACT", "TESSDATA_PREFIX", "PYTHONPATH", "VIRTUAL_ENV"}}
    with tempfile.TemporaryDirectory(prefix="ocready-smoke-") as directory:
        output = Path(directory) / "result.json"
        subprocess.run([str(binary), str(root / "assets" / "sample-bilingual.png"), "--json", "--layout", "sparse",
                        "--output", str(output)], cwd=directory, env=env, check=True, timeout=90)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert "مرحبا بالعالم" in result["text"], result["text"]
        assert "screenshots" in result["text"], result["text"]
        assert result["words"], "No real word geometry"
        print(f"Compiled OCR passed: {len(result['words'])} words; sampled {result['peak_rss'] / 1e6:.1f} MB RSS")


if __name__ == "__main__":
    main()
