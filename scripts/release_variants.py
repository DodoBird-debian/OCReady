"""Verify both platform artifacts and every embedded method before a model release."""
import argparse
import json
import re
import shutil
from pathlib import Path

from ocready.core.editions import EDITIONS
from ocready.engines.vision_adapters import ADAPTERS
from scripts.corpus_identity import load_corpus_identity
from scripts.provenance import file_sha256
from scripts.release_assets import SCENARIOS, verify_execution_environment
from scripts.smoke_binary import embedded_selections
from scripts.variants import MODEL_VARIANTS, VISION_VARIANTS


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def embedded_assets(profile: dict) -> dict[tuple[str, str], dict]:
    """Compare model content/capabilities, independently of platform executables."""
    assets = {}
    for method, key, hashes in (("vision", "embedded_models", ("model_sha256", "projector_sha256")),
                                ("neural", "embedded_neural", ("detector_sha256", "recognizer_sha256", "dictionary_sha256"))):
        records = profile.get(key, [])
        if not isinstance(records, list) or records and method not in profile.get("methods", []):
            raise ValueError("Invalid embedded model inventory.")
        for record in records:
            if (not isinstance(record, dict) or not isinstance(record.get("id"), str)
                    or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", record["id"])
                    or record.get("languages") not in {"ara", "eng", "ara+eng"}):
                raise ValueError("Invalid embedded model identity or language capability.")
            identity = {"languages": record["languages"]}
            if method == "vision":
                adapter = record.get("adapter", "llama.cpp")
                if not isinstance(adapter, str) or adapter not in ADAPTERS:
                    raise ValueError("Invalid embedded vision adapter identity.")
                identity["adapter"] = adapter
            else:
                if record.get("geometry") != "line":
                    raise ValueError("Invalid embedded neural geometry identity.")
                identity["geometry"] = record["geometry"]
            for name in hashes:
                digest = record.get(name)
                optional = method == "vision" and name == "projector_sha256" and adapter != "llama.cpp"
                if not (optional and digest == "") and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                    raise ValueError("Missing or invalid embedded model asset digest.")
                identity[name] = digest
            choice = (method, record["id"])
            if choice in assets:
                raise ValueError("Duplicate embedded model identity.")
            assets[choice] = identity
    if not any(method == "neural" and row["languages"] == "ara+eng" for (method, _), row in assets.items()):
        raise ValueError("A model release needs an embedded bilingual neural model.")
    return assets


def verify_variants(root: Path, revision: str, edition: str, variant: str) -> list[dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Supply the full source revision.")
    if edition not in {"everyday", "studio"} or variant not in MODEL_VARIANTS:
        raise ValueError("Choose a supported model edition and variant.")
    policy = EDITIONS[edition]
    verified = []
    expected_choices = None
    expected_assets = None
    corpus, expected_corpus, legacy_checksums = load_corpus_identity(Path(__file__).resolve().parents[1] / "assets/accuracy/manifest.json")
    expected_cases = {case["id"]: (case["language"], case["expected"]) for case in corpus["cases"]}
    for platform, suffix, runtime_platform in (("Linux", "linux-x86_64", "linux"),
                                               ("Windows", "windows-amd64.exe", "win32")):
        folder = root / f"OCReady-{edition}-{variant}-{platform}"
        binary = folder / "dist" / f"{edition}-{variant}" / f"OCReady-{edition}-{variant}-{suffix}"
        manifest = binary.parent / "build-manifest.json"
        profile = read_json(manifest)
        source = profile.get("source", {})
        if (source.get("revision") != revision or source.get("dirty") is not False
                or not re.fullmatch(r"[0-9a-f]{64}", source.get("tree_sha256", ""))
                or profile.get("edition") != edition or profile.get("variant") != variant):
            raise ValueError(f"{binary.name}: wrong or unclean source/variant identity.")
        assets = embedded_assets(profile)
        if variant == "multimodal-json" and any(row.get("adapter") != "json-cli-v1" for (method, _), row in assets.items() if method == "vision"):
            raise ValueError("The JSON multimodal variant needs the JSON runtime for every vision choice.")
        if expected_assets is not None and assets != expected_assets:
            raise ValueError("The platform artifacts contain different model assets or capabilities.")
        expected_assets = assets
        choices = embedded_selections(profile)
        if (not choices or len(choices) != len(set(choices)) or not any(m == "neural" for m, _ in choices)
                or any(m not in {"tesseract-fast", "tesseract-best", "neural", "vision"}
                       or pack and not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", pack) for m, pack in choices)
                or variant == "neural" and any(m != "neural" for m, _ in choices)):
            raise ValueError("A model release needs unique embedded choices including bilingual neural OCR.")
        if variant != "neural" and not {("tesseract-fast", ""), ("tesseract-best", "")} <= set(choices):
            raise ValueError("The combined variant is missing classical engines.")
        if variant in VISION_VARIANTS and sum(m == "vision" for m, _ in choices) < (2 if edition == "studio" else 1):
            raise ValueError("The multimodal variant is missing embedded vision choices.")
        if expected_choices is not None and set(choices) != expected_choices:
            raise ValueError("The platform artifacts contain different engine/model choices.")
        expected_choices = set(choices)
        digest = file_sha256(binary)
        checksum = Path(str(binary) + ".sha256")
        if checksum.read_text(encoding="utf-8").split() != [digest, binary.name]:
            raise ValueError(f"{binary.name}: executable checksum mismatch.")
        reports = {}
        for path in sorted((folder / "test-output").glob("packaged-*.json")):
            report = read_json(path)
            method, pack_id = report.get("requested_method"), report.get("requested_pack_id") or ""
            # The first neural-only workflow predates explicit selection fields.
            # Its actual engine identity must still match in every workload.
            if method is None and len(choices) == 1:
                method, pack_id = choices[0]
            choice = (method, pack_id)
            if choice not in choices or choice in reports:
                raise ValueError("Unexpected or duplicate resource selection evidence.")
            if (report.get("binary_sha256") != digest or report.get("build_profile") != profile
                    or report.get("binary") is not True or report.get("platform") != runtime_platform
                    or report.get("source") != source or report.get("sources_changed_during_run") is not False
                    or report.get("binary_changed_during_run") is not False):
                raise ValueError(f"{binary.name}: resource provenance mismatch.")
            rows = report.get("scenarios", [])
            if len(rows) != 4 or {row.get("scenario") for row in rows} != SCENARIOS:
                raise ValueError("Every embedded choice needs all four packaged resource scenarios.")
            verify_execution_environment(report, profile, runtime_platform)
            engine = f"{method}:{pack_id}" if pack_id else method
            for row in rows:
                details = row.get("details", {})
                if (row.get("edition") != edition or row.get("budget_bytes") != policy.budget
                        or row.get("below_budget") is not True or row.get("exit_code") != 0
                        or not 0 < row.get("peak_rss_bytes", 0) < policy.budget or row.get("error")
                        or details.get("error") or details.get("engine") != engine
                        or method != "vision" and not details.get("words", 0)):
                    raise ValueError(f"{binary.name}: failed or wrong-engine packaged resource evidence.")
            reports[choice] = path
        if set(reports) != set(choices):
            raise ValueError("Resource evidence is missing for one or more embedded choices.")
        accuracy = folder / "test-output/neural-accuracy.json"
        evaluation = read_json(accuracy)
        score = evaluation.get("summaries", {}).get("neural", {})
        cases = evaluation.get("cases", [])
        if (evaluation.get("source") != source or evaluation.get("sources_changed_during_run") is not False
                or score.get("completed") != 11 or score.get("errors") != 0 or score.get("skipped") != 0
                or len(cases) != 11 or any(row.get("status") != "ok" or row.get("method") != "neural" for row in cases)
                or not re.fullmatch(r"[0-9a-f]{64}", evaluation.get("corpus_sha256", ""))):
            raise ValueError("Complete matching-source bilingual neural accuracy evidence is required.")
        content_digest = evaluation.get("corpus_content_sha256")
        if (content_digest is not None and content_digest != expected_corpus
                or content_digest is None and evaluation["corpus_sha256"] not in legacy_checksums
                or {row.get("case"): (row.get("language"), row.get("expected")) for row in cases} != expected_cases
                or len({row.get("case") for row in cases}) != len(cases)
                or any(row.get("engine") not in {f"neural:{pack}" for method, pack in choices if method == "neural"} for row in cases)):
            raise ValueError("The accuracy reports do not match this checkout's corpus content and model choices.")
        verified.append({"binary": binary, "manifest": manifest, "checksum": checksum, "accuracy": accuracy,
                         "reports": reports, "sha256": digest, "platform": platform,
                         "peak_rss_bytes": max(row["peak_rss_bytes"] for path in reports.values()
                                               for row in read_json(path)["scenarios"]),
                         "budget_bytes": policy.budget, "neural_accuracy": score, "embedded_assets": assets,
                         "corpus_content_sha256": expected_corpus})
    return verified


def prepare_release(root: Path, output: Path, revision: str, edition: str, variant: str, run_id: int) -> None:
    if run_id <= 0:
        raise ValueError("Supply the successful workflow run ID.")
    verified = verify_variants(root, revision, edition, variant)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory; existing release files are kept.")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"source_revision": revision, "workflow_run_id": run_id, "edition": edition, "variant": variant,
               "corpus_content_sha256": verified[0]["corpus_content_sha256"],
               "embedded_assets": [{"method": method, "id": pack_id, **identity}
                                   for (method, pack_id), identity in sorted(verified[0]["embedded_assets"].items())],
               "artifacts": []}
    for record in verified:
        binary = record["binary"]
        files = [(binary, binary.name), (record["checksum"], binary.name + ".sha256"),
                 (record["manifest"], binary.name + ".manifest.json"),
                 (record["accuracy"], binary.name + ".neural-accuracy.json")]
        for (method, pack_id), report in record["reports"].items():
            label = method + ("-" + pack_id if pack_id else "")
            files.append((report, binary.name + "." + label + ".benchmarks.json"))
        for source, name in files:
            shutil.copyfile(source, output / name)
        if record["platform"] == "Linux":
            (output / binary.name).chmod(0o755)
        summary["artifacts"].append({key: record[key] for key in
                                    ("platform", "sha256", "peak_rss_bytes", "budget_bytes", "neural_accuracy")}
                                   | {"filename": binary.name, "choices": [list(choice) for choice in record["reports"]]})
    (output / "release-evidence.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    notes = [f"OCReady {edition.title()} · {variant} preview", "", f"Source `{revision}` · workflow `{run_id}`.", "",
             "Two native single-file executables containing the model worker and weights. Python and a separate model download are not required to run them.", "",
             "Open, paste, or capture an image; choose Recognize text, then copy. Neural OCR reads Arabic + English and links whole detected lines to the picture. Click a line or drag over several lines to select them. Manual edits unlink the source until recognition runs again.", ""]
    if variant == "neural":
        notes += ["This variant includes neural OCR only. Choose a classical default edition for individual-word boxes; the neural model supplies whole-line geometry.", ""]
    else:
        notes += ["Fast and Precision provide individual-word boxes. Installed local models are chosen in the method selector and run one at a time. Vision transcription has no invented source locations and can omit or invent text.", ""]
    notes += ["These packs use CPU inference. Compatible CUDA runners can be configured separately; Windows neural GPU inference is not certified by these artifacts.", "",
              "| Platform | Largest observed process-tree RSS | Budget |", "| --- | ---: | ---: |"]
    for item in summary["artifacts"]:
        notes.append(f"| {item['platform']} | {item['peak_rss_bytes'] / 1e6:.1f} MB | {item['budget_bytes'] / 1e6:g} MB |")
    notes += ["", "The attached reports cover four packaged CLI/GUI resource workloads for every embedded choice. They do not prove a universal whole-application hard memory ceiling. CUDA VRAM is separate. The eleven-image synthetic accuracy corpus is a regression tool; inspect digits and Arabic diacritics carefully.", "",
              "Linux x86_64 binaries are built on Ubuntu 22.04; make the downloaded file executable with chmod +x, then open it. On Windows 11 open the amd64 .exe. Actual interactive KDE/Windows snipping still needs desktop validation.", ""]
    (output / "RELEASE-NOTES.md").write_text("\n".join(notes), encoding="utf-8")
    (output / "CHECKSUMS.sha256").write_text("\n".join(f"{file_sha256(path)}  {path.name}" for path in sorted(output.iterdir())) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--edition", choices=("everyday", "studio"), required=True)
    parser.add_argument("--variant", choices=MODEL_VARIANTS, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    try:
        prepare_release(args.artifacts, args.output, args.revision, args.edition, args.variant, args.run_id)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Model release preparation failed: {exc}\n")
    print(f"Verified both platforms and every embedded choice in {args.output}")


if __name__ == "__main__":
    main()
