"""Execute compiled onefile methods without a source-runtime override."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from ocready.core.timeouts import observed_workload_timeout_seconds
from scripts.host_diagnostics import host_identity
from scripts.packaged_environment import gui_test_platform, runtime_test_environment
from scripts.provenance import file_sha256, source_record


def embedded_selections(profile: dict) -> list[tuple[str, str]]:
    selections = []
    for method in profile["methods"]:
        if method in {"vision", "neural"}:
            packs = profile.get("embedded_models" if method == "vision" else "embedded_neural", [])
            selections.extend((method, pack["id"]) for pack in packs)
        else:
            selections.append((method, ""))
    return selections


def sample_languages(profile: dict, method: str, pack_id: str) -> str:
    if method not in {"vision", "neural"}:
        return "ara+eng"
    packs = profile.get("embedded_models" if method == "vision" else "embedded_neural", [])
    selected = pack_id or profile.get("default_model" if method == "vision" else "default_neural")
    pack = next((pack for pack in packs if pack["id"] == selected), None) if selected else next(iter(packs), None)
    if not pack or pack.get("languages") not in {"ara+eng", "ara", "eng"}:
        raise ValueError("The selected embedded pack needs a supported language declaration.")
    return pack["languages"]


def assert_sample_text(value: str, languages: str, *, vision: bool = False) -> None:
    if languages not in {"ara+eng", "ara", "eng"}:
        raise ValueError("Unsupported sample language declaration.")
    # Tiny English packs must not gain an Arabic claim. A bilingual VLM must
    # actually read Arabic too; harmless optional marks are ignored only for
    # this basic presence probe, separately from corpus CER/WER evaluation.
    arabic = value
    if vision:
        arabic = "".join(c for c in unicodedata.normalize("NFKC", value) if unicodedata.category(c) != "Mn" and c != "\u0640")
    arabic_phrases = ("مرحبا بالعالم", "اللغة العربية واللغة الإنجليزية") if vision else ("مرحبا بالعالم",)
    if "ara" in languages and not any(phrase in arabic for phrase in arabic_phrases):
        raise AssertionError("The declared Arabic method did not read an expected Arabic sample phrase.")
    if "eng" in languages and "screenshots" not in value:
        raise AssertionError("The declared English method did not read the English sample phrase.")


def run_checked(command: list[str], *, timeout: float | None = None, diagnostic: Path | None = None, **kwargs) -> None:
    """Keep diagnostic timeouts/interruption from orphaning a onefile child."""
    if diagnostic is not None:
        # Redirected handles also preserve diagnostics from Windows attach-mode
        # executables when their CI parent has no usable console.
        with tempfile.TemporaryFile() as log:
            try:
                run_checked(command, timeout=timeout, stdout=log, stderr=subprocess.STDOUT, **kwargs)
            finally:
                size = log.seek(0, 2)
                log.seek(max(0, size - 65536))
                tail = log.read(65536).decode("utf-8", errors="replace")
                diagnostic.parent.mkdir(parents=True, exist_ok=True)
                diagnostic.write_text(tail, encoding="utf-8")
                if tail:
                    print(tail.encode("ascii", errors="backslashreplace").decode("ascii"), flush=True)
        return
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
    # Persist host and exact binary identity before the first model can fail.
    host = root / "test-output" / (f"host-{profile['edition']}" + ("-" + profile["variant"] if profile.get("variant") else "") + ".json")
    host.parent.mkdir(parents=True, exist_ok=True)
    host.write_text(json.dumps({"host": host_identity(), "binary_name": binary.name,
                                "binary_sha256": file_sha256(binary), "build_profile": profile,
                                "controller_source": source_record(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selections = embedded_selections(profile) if args.all_methods else [(profile["methods"][0], "")]
    if not selections:
        raise RuntimeError("No embedded methods are available to test.")
    for method, pack_id in selections:
        vision = method == "vision"
        neural = method == "neural"
        languages = sample_languages(profile, method, pack_id)
        selection = ["--method", method]
        if pack_id:
            selection += ["--pack-id", pack_id]
        label = method + ("-" + pack_id if pack_id else "")
        evidence_name = f"gui-{profile['edition']}" + ("-" + profile["variant"] if profile.get("variant") else "") + "-" + label
        evidence = root / "test-output" / evidence_name
        evidence.parent.mkdir(parents=True, exist_ok=True)
        deadline = observed_workload_timeout_seconds(method)
        with tempfile.TemporaryDirectory(prefix="ocready-smoke-") as temporary:
            env = runtime_test_environment(Path(temporary) / "runtime-العربية")
            output = Path(temporary) / "result.json"
            run_checked([str(binary), str(root / "assets/sample-bilingual.png"), "--json", "--layout", "sparse",
                         "--output", str(output), *selection], cwd=temporary, env=env, timeout=deadline,
                        diagnostic=evidence.with_name(evidence.name.replace("gui-", "cli-", 1)).with_suffix(".log"))
            result = json.loads(output.read_text(encoding="utf-8"))
            assert not result.get("error"), result
            assert result["engine"] == (f"{method}:{pack_id}" if pack_id else method) or not pack_id and result["engine"].startswith(method), result
            assert result.get("language") == languages, result
            assert_sample_text(result["text"], languages, vision=vision)
            assert bool(result["words"]) != vision, "Unexpected geometry for this method"
            if neural:
                assert result["geometry"] == "line", result
            print(f"{label}: compiled OCR passed; {len(result['words'])} regions; sampled {result['peak_rss'] / 1e6:.1f} MB RSS", flush=True)
            output = Path(temporary) / "gui-result.json"
            gui_env = {**env, "QT_QPA_PLATFORM": gui_test_platform(), "XDG_CONFIG_HOME": str(Path(temporary) / "config"),
                       "APPDATA": str(Path(temporary) / "config")}
            try:
                run_checked([str(binary), str(root / "assets/sample-bilingual.png"),
                             "--ui-smoke-output", str(output), *selection], cwd=temporary, env=gui_env, timeout=deadline,
                            diagnostic=evidence.with_suffix(".log"))
            finally:
                for suffix in (".json", ".png"):
                    if output.with_suffix(suffix).is_file():
                        shutil.copyfile(output.with_suffix(suffix), evidence.with_suffix(suffix))
            gui = json.loads(output.read_text(encoding="utf-8"))
            assert not gui["error"], gui
            assert gui.get("qt_platform") == gui_test_platform(), gui
            assert gui.get("clipboard_copy_verified") is True, gui
            if profile.get("validation_policy", {}).get("clipboard_image_input"):
                assert gui.get("input_route") == "clipboard", gui
            assert gui["result"]["engine"] == result["engine"], gui
            assert gui["result"].get("language") == languages, gui
            assert_sample_text(gui["text"], languages, vision=vision)
            if vision:
                assert not gui["linked"] and gui["words"] == 0, gui
            else:
                assert gui.get("source_selection_verified") is True, gui
                assert gui["linked"] and gui["words"] >= (1 if neural else 25), gui
            gui["build_profile"] = profile
            gui["requested_method"], gui["requested_pack_id"] = method, pack_id
            output.write_text(json.dumps(gui, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            shutil.copyfile(output, evidence.with_suffix(".json"))
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
