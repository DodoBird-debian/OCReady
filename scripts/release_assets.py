"""Verify six default Actions builds and prepare a flat release directory."""
import argparse
import json
import re
import shutil
from pathlib import Path

from ocready.core.editions import EDITIONS
from scripts.provenance import file_sha256

SCENARIOS = {"sample", "dark", "max-pixels", "gui-onefile"}


def verify_execution_environment(evidence: dict, profile: dict, runtime_platform: str) -> None:
    requirement = profile.get("validation_policy")
    environment = evidence.get("execution_environment")
    if requirement is None and environment is None:
        return  # Older releases retain their original, narrower validation scope.
    if requirement is not None and (not isinstance(requirement, dict)
            or type(requirement.get("portable_runtime_environment")) is not int or requirement.get("portable_runtime_environment") != 1
            or requirement.get("native_gui_backend") is not True or requirement.get("unicode_paths") is not True
            or "clipboard_image_input" in requirement and requirement["clipboard_image_input"] is not True):
        raise ValueError("Unsupported packaged validation policy.")
    expected_gui = {"windows"} if runtime_platform == "win32" else {"xcb", "wayland"}
    if (not isinstance(environment, dict) or environment.get("policy") != "isolated-runtime-v1"
            or environment.get("path_scope") != "OS system directories"
            or environment.get("unicode_runtime_temp") is not True or environment.get("private_configuration") is not True
            or environment.get("development_overrides_removed") is not True
            or not isinstance(environment.get("gui_platform"), str) or environment.get("gui_platform") not in expected_gui):
        raise ValueError("Packaged release needs isolated runtimes, Unicode paths and the native GUI backend.")
    gui = [row for row in evidence.get("scenarios", []) if row.get("scenario") == "gui-onefile"]
    if len(gui) != 1 or gui[0].get("details", {}).get("qt_platform") != environment["gui_platform"]:
        raise ValueError("The GUI result did not confirm the requested native windowing backend.")
    if requirement and requirement.get("clipboard_image_input") is True and gui[0].get("details", {}).get("input_route") != "clipboard":
        raise ValueError("The GUI resource workload did not confirm clipboard image input.")


def verify_artifacts(root: Path, revision: str) -> list[dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Supply the full 40-character source revision.")
    verified = []
    for edition, policy in EDITIONS.items():
        for platform, suffix, runtime_platform in (("Linux", "linux-x86_64", "linux"),
                                                   ("Windows", "windows-amd64.exe", "win32")):
            folder = root / f"OCReady-{edition}-{platform}"
            binary = folder / "dist" / edition / f"OCReady-{edition}-{suffix}"
            manifest = binary.parent / "build-manifest.json"
            report = folder / "test-output" / f"packaged-{edition}.json"
            profile = json.loads(manifest.read_text(encoding="utf-8"))
            source = profile.get("source", {})
            if source.get("revision") != revision or source.get("dirty") is not False:
                raise ValueError(f"{binary.name}: source revision is wrong or unclean.")
            if not re.fullmatch(r"[0-9a-f]{64}", source.get("tree_sha256", "")):
                raise ValueError(f"{binary.name}: missing source-content digest.")
            required_methods = {"tesseract-fast"} | ({"tesseract-best"} if edition != "pocket" else set())
            if profile.get("edition") != edition or not required_methods <= set(profile.get("methods", [])):
                raise ValueError(f"{binary.name}: default bilingual methods are missing.")
            digest = file_sha256(binary)
            checksum = Path(str(binary) + ".sha256")
            if checksum.read_text(encoding="utf-8").split() != [digest, binary.name]:
                raise ValueError(f"{binary.name}: executable checksum mismatch.")
            evidence = json.loads(report.read_text(encoding="utf-8"))
            if (evidence.get("binary_sha256") != digest or evidence.get("build_profile") != profile
                    or evidence.get("source") != source
                    or evidence.get("binary") is not True or evidence.get("platform") != runtime_platform
                    or evidence.get("sources_changed_during_run") is not False
                    or evidence.get("binary_changed_during_run") is not False):
                raise ValueError(f"{binary.name}: benchmark provenance does not match.")
            rows = evidence.get("scenarios", [])
            if len(rows) != 4 or {row.get("scenario") for row in rows} != SCENARIOS:
                raise ValueError(f"{binary.name}: all four packaged scenarios are required.")
            verify_execution_environment(evidence, profile, runtime_platform)
            for row in rows:
                if (row.get("edition") != edition or row.get("budget_bytes") != policy.budget
                        or row.get("below_budget") is not True or row.get("exit_code") != 0
                        or not 0 < row.get("peak_rss_bytes", 0) < policy.budget
                        or row.get("details", {}).get("error") or row.get("error")):
                    raise ValueError(f"{binary.name}: failed packaged {row.get('scenario')} evidence.")
            verified.append({"binary": binary, "manifest": manifest, "report": report, "checksum": checksum,
                             "sha256": digest, "edition": edition, "platform": platform,
                             "peak_rss_bytes": max(row["peak_rss_bytes"] for row in rows),
                             "budget_bytes": policy.budget})
    return verified


def prepare_release(root: Path, output: Path, revision: str, run_id: int) -> None:
    if run_id <= 0:
        raise ValueError("Supply the successful workflow run ID.")
    verified = verify_artifacts(root, revision)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory; existing release files are kept.")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"source_revision": revision, "workflow_run_id": run_id, "artifacts": []}
    for record in verified:
        binary = record["binary"]
        for source, name in ((binary, binary.name), (record["checksum"], binary.name + ".sha256"),
                             (record["manifest"], binary.name + ".manifest.json"),
                             (record["report"], binary.name + ".benchmarks.json")):
            shutil.copyfile(source, output / name)
        if record["platform"] == "Linux":
            (output / binary.name).chmod(0o755)
        summary["artifacts"].append({key: record[key] for key in ("edition", "platform", "sha256", "peak_rss_bytes", "budget_bytes")}
                                    | {"filename": binary.name})
    (output / "release-evidence.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    notes = ["Experimental OCReady prerelease", "", f"Source: `{revision}` · workflow run `{run_id}`.", "",
             "Six native single-file executables with offline Arabic + English OCR, image cleanup, a split image/text workspace, and source-word selection. Python is not required to run them.", "",
             "Choose Pocket for the 350 MB target, Everyday for 1 GB, or Studio for 4 GB. Everyday and Studio accept separately configured local vision packs. Vision model weights are not included in these default artifacts.", "",
             "| Edition | Platform | Largest observed workload RSS | Target |", "| --- | --- | ---: | ---: |"]
    for item in summary["artifacts"]:
        notes.append(f"| {item['edition'].title()} | {item['platform']} | {item['peak_rss_bytes'] / 1e6:.1f} MB | {item['budget_bytes'] / 1e6:g} MB |")
    notes += ["", "Measurements cover the documented packaged CLI/GUI workloads and their child processes. They do not certify a universal whole-application allocation ceiling; GPU VRAM is separate.", "",
              "Linux x86_64 builds are made on Ubuntu 22.04. After downloading, make the file executable with `chmod +x OCReady-*-linux-x86_64`, then open it. On Windows 11, open the downloaded amd64 `.exe`.", "",
              "Open, paste, or capture an image; choose Recognize text; select and copy. Use Fast/Precision for located Arabic + English words. The optional small vision model tested separately supports English only.", "",
              "Actual interactive KDE/Windows snipping and Windows GPU inference still need desktop validation. Use the attached checksums, manifests, benchmark reports, and release-evidence.json to inspect this build.", ""]
    (output / "RELEASE-NOTES.md").write_text("\n".join(notes), encoding="utf-8")
    checksums = [f"{file_sha256(path)}  {path.name}" for path in sorted(output.iterdir()) if path.is_file()]
    (output / "CHECKSUMS.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    try:
        prepare_release(args.artifacts, args.output, args.revision, args.run_id)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Release preparation failed: {exc}\n")
    print(f"Verified and prepared six editions in {args.output}")


if __name__ == "__main__":
    main()
