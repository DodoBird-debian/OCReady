"""Execute compiled onefile methods without a source-runtime override."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ocready.core.timeouts import observed_workload_timeout_seconds


def embedded_selections(profile: dict) -> list[tuple[str, str]]:
    selections = []
    for method in profile["methods"]:
        if method in {"vision", "neural"}:
            packs = profile.get("embedded_models" if method == "vision" else "embedded_neural", [])
            selections.extend((method, pack["id"]) for pack in packs)
        else:
            selections.append((method, ""))
    return selections


def run_checked(command: list[str], *, timeout: float | None = None, **kwargs) -> None:
    """Keep diagnostic timeouts/interruption from orphaning a onefile child."""
    child = subprocess.Popen(command, **kwargs)
    try:
        code = child.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    finally:
        if child.poll() is None:
            from ocready.core.memory import stop_tree
            stop_tree(child.pid)
        child.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--all-methods", action="store_true", help="Run CLI, native GUI and optional resource workloads for every embedded choice")
    args = parser.parse_args()
    directory = args.directory.resolve()
    binary = next(p for p in directory.glob("OCReady-*") if p.is_file() and not p.name.endswith(".sha256"))
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((binary.parent / "build-manifest.json").read_text(encoding="utf-8"))
    selections = embedded_selections(profile) if args.all_methods else [(profile["methods"][0], "")]
    if not selections:
        raise RuntimeError("No embedded methods are available to test.")
    env = {key: value for key, value in os.environ.items()
           if key not in {"OCREADY_RUNTIME", "OCREADY_TESSERACT", "TESSDATA_PREFIX", "PYTHONPATH", "VIRTUAL_ENV"}}
    for method, pack_id in selections:
        vision = method == "vision"
        neural = method == "neural"
        selection = ["--method", method]
        if pack_id:
            selection += ["--pack-id", pack_id]
        label = method + ("-" + pack_id if pack_id else "")
        deadline = observed_workload_timeout_seconds(method)
        with tempfile.TemporaryDirectory(prefix="ocready-smoke-") as temporary:
            output = Path(temporary) / "result.json"
            run_checked([str(binary), str(root / "assets/sample-bilingual.png"), "--json", "--layout", "sparse",
                         "--output", str(output), *selection], cwd=temporary, env=env, timeout=deadline)
            result = json.loads(output.read_text(encoding="utf-8"))
            assert not result.get("error"), result
            assert result["engine"] == (f"{method}:{pack_id}" if pack_id else method) or not pack_id and result["engine"].startswith(method), result
            if not vision:
                assert "مرحبا بالعالم" in result["text"], result["text"]
            assert "screenshots" in result["text"], result["text"]
            assert bool(result["words"]) != vision, "Unexpected geometry for this method"
            if neural:
                assert result["geometry"] == "line", result
            print(f"{label}: compiled OCR passed; {len(result['words'])} regions; sampled {result['peak_rss'] / 1e6:.1f} MB RSS", flush=True)
            output = Path(temporary) / "gui-result.json"
            gui_env = {**env, "QT_QPA_PLATFORM": "offscreen", "XDG_CONFIG_HOME": str(Path(temporary) / "config"),
                       "APPDATA": str(Path(temporary) / "config")}
            run_checked([str(binary), str(root / "assets/sample-bilingual.png"),
                         "--ui-smoke-output", str(output), *selection], cwd=temporary, env=gui_env, timeout=deadline)
            gui = json.loads(output.read_text(encoding="utf-8"))
            assert not gui["error"], gui
            assert gui["result"]["engine"] == result["engine"], gui
            if vision:
                assert not gui["linked"] and gui["words"] == 0, gui
                assert "screenshots" in gui["text"], gui["text"]
            else:
                assert gui["linked"] and gui["words"] >= (1 if neural else 25), gui
                assert "مرحبا بالعالم" in gui["text"], gui["text"]
            print(f"{label}: compiled native GUI passed; {gui['words']} linked regions; {gui['rss'] / 1e6:.1f} MB idle RSS", flush=True)
        if args.benchmark:
            # Preserve the original default-edition path used by release verification.
            suffix = "-" + profile.get("variant", "") if profile.get("variant") else ""
            suffix += "-" + label if args.all_methods else ""
            report = root / "test-output" / f"packaged-{profile['edition']}{suffix}.json"
            run_checked([sys.executable, str(root / "scripts/benchmark.py"),
                         "--edition", profile["edition"], "--binary", str(binary), "--output", str(report), *selection], cwd=root)


if __name__ == "__main__":
    main()
