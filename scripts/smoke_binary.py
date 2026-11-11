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
    profile = json.loads((binary.parent / "build-manifest.json").read_text())
    vision_only = profile["methods"][0] == "vision"
    neural_default = profile["methods"][0] == "neural"
    env = {key: value for key, value in os.environ.items()
           if key not in {"OCREADY_RUNTIME", "OCREADY_TESSERACT", "TESSDATA_PREFIX", "PYTHONPATH", "VIRTUAL_ENV"}}
    with tempfile.TemporaryDirectory(prefix="ocready-smoke-") as directory:
        output = Path(directory) / "result.json"
        subprocess.run([str(binary), str(root / "assets" / "sample-bilingual.png"), "--json", "--layout", "sparse",
                        "--output", str(output)], cwd=directory, env=env, check=True, timeout=90)
        result = json.loads(output.read_text(encoding="utf-8"))
        if not vision_only:
            assert "مرحبا بالعالم" in result["text"], result["text"]
        assert "screenshots" in result["text"], result["text"]
        assert bool(result["words"]) != vision_only, "Unexpected word geometry for this method"
        if neural_default:
            assert result["geometry"] == "line", result
        print(f"Compiled OCR passed: {len(result['words'])} located regions; sampled {result['peak_rss'] / 1e6:.1f} MB RSS")
        output = Path(directory) / "gui-result.json"
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["XDG_CONFIG_HOME"] = str(Path(directory) / "config")
        env["APPDATA"] = str(Path(directory) / "config")
        subprocess.run([str(binary), str(root / "assets" / "sample-bilingual.png"),
                        "--ui-smoke-output", str(output)], cwd=directory, env=env, check=True, timeout=150)
        gui = json.loads(output.read_text(encoding="utf-8"))
        assert not gui["error"], gui
        if vision_only:
            assert not gui["linked"] and gui["words"] == 0, gui
            assert "screenshots" in gui["text"], gui["text"]
        else:
            assert gui["linked"] and gui["words"] >= (1 if neural_default else 25), gui
            assert "مرحبا بالعالم" in gui["text"], gui["text"]
        print(f"Compiled native GUI passed: {gui['words']} linked regions; {gui['rss'] / 1e6:.1f} MB idle RSS")
    if "--benchmark" in sys.argv:
        profile = json.loads((binary.parent / "build-manifest.json").read_text())
        report = root / "test-output" / f"packaged-{profile['edition']}.json"
        subprocess.run([sys.executable, str(root / "scripts" / "benchmark.py"),
                        "--edition", profile["edition"], "--binary", str(binary), "--output", str(report)],
                       cwd=root, check=True)


if __name__ == "__main__":
    main()
