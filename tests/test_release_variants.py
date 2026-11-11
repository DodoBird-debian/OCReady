import json
from pathlib import Path

import pytest

from scripts.corpus_identity import load_corpus_identity
from scripts.provenance import file_sha256
from scripts.release_assets import SCENARIOS
from scripts.release_variants import prepare_release, verify_variants
from scripts.smoke_binary import embedded_selections

REVISION = "a" * 40
CORPUS, CORPUS_DIGEST, LEGACY_CORPUS_DIGESTS = load_corpus_identity(Path(__file__).resolve().parents[1] / "assets/accuracy/manifest.json")


@pytest.fixture
def artifacts(tmp_path):
    def create(variant="multimodal"):
        for platform, suffix, runtime_platform in (("Linux", "linux-x86_64", "linux"), ("Windows", "windows-amd64.exe", "win32")):
            folder = tmp_path / f"OCReady-everyday-{variant}-{platform}"
            binary = folder / f"dist/everyday-{variant}" / f"OCReady-everyday-{variant}-{suffix}"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"synthetic binary")
            digest = file_sha256(binary)
            Path(str(binary) + ".sha256").write_text(f"{digest}  {binary.name}\n")
            source = {"revision": REVISION, "dirty": False, "tree_sha256": ("b" if platform == "Linux" else "c") * 64}
            profile = {"edition": "everyday", "variant": variant, "source": source,
                       "methods": ["neural"] if variant == "neural" else ["neural", "tesseract-fast", "tesseract-best", "vision"],
                       "embedded_models": [] if variant == "neural" else [{"id": "small", "languages": "eng",
                           "model_sha256": "1" * 64, "projector_sha256": "2" * 64}],
                       "embedded_neural": [{"id": "bilingual", "languages": "ara+eng", "geometry": "line",
                           "detector_sha256": "3" * 64, "recognizer_sha256": "4" * 64, "dictionary_sha256": "5" * 64}]}
            (binary.parent / "build-manifest.json").write_text(json.dumps(profile))
            reports = folder / "test-output"
            reports.mkdir()
            for method, pack in embedded_selections(profile):
                engine = method + (":" + pack if pack else "")
                report = {"binary": True, "binary_sha256": digest, "build_profile": profile, "source": source,
                          "platform": runtime_platform, "sources_changed_during_run": False, "binary_changed_during_run": False,
                          "requested_method": method, "requested_pack_id": pack,
                          "scenarios": [{"edition": "everyday", "budget_bytes": 1_000_000_000, "peak_rss_bytes": 500_000_000,
                                         "exit_code": 0, "below_budget": True, "scenario": scenario,
                                         "details": {"engine": engine, "words": 0 if method == "vision" else 4}} for scenario in SCENARIOS]}
                (reports / f"packaged-{method}-{pack}.json").write_text(json.dumps(report))
            accuracy = {"source": source, "sources_changed_during_run": False, "corpus_sha256": next(iter(LEGACY_CORPUS_DIGESTS)),
                        "corpus_content_sha256": CORPUS_DIGEST,
                        "summaries": {"neural": {"completed": 11, "errors": 0, "skipped": 0, "cer": .04, "wer": .08}},
                        "cases": [{"status": "ok", "method": "neural", "engine": "neural:bilingual", "case": row["id"],
                                   "language": row["language"], "expected": row["expected"]} for row in CORPUS["cases"]]}
            (reports / "neural-accuracy.json").write_text(json.dumps(accuracy))
        return tmp_path
    return create


def test_model_release_checks_both_platforms_and_all_choices(artifacts, tmp_path):
    root = artifacts()
    output = tmp_path / "release"
    prepare_release(root, output, REVISION, "everyday", "multimodal", 123)
    evidence = json.loads((output / "release-evidence.json").read_text())
    assert len(evidence["artifacts"]) == 2
    assert all(len(row["choices"]) == 4 for row in evidence["artifacts"])
    assert evidence["embedded_assets"][0]["method"] == "neural"
    assert evidence["embedded_assets"][1]["adapter"] == "llama.cpp"
    assert evidence["corpus_content_sha256"] == CORPUS_DIGEST
    assert len(list(output.glob("*.benchmarks.json"))) == 8
    for line in (output / "CHECKSUMS.sha256").read_text().splitlines():
        digest, name = line.split()
        assert file_sha256(output / name) == digest
    with pytest.raises(ValueError, match="empty output"):
        prepare_release(root, output, REVISION, "everyday", "multimodal", 123)


def test_old_single_neural_report_still_requires_actual_engine_identity(artifacts):
    root = artifacts("neural")
    for report in root.glob("*/test-output/packaged-*.json"):
        data = json.loads(report.read_text())
        data.pop("requested_method")
        data.pop("requested_pack_id")
        report.write_text(json.dumps(data))
    assert len(verify_variants(root, REVISION, "everyday", "neural")) == 2
    report = next(root.glob("*/test-output/packaged-*.json"))
    data = json.loads(report.read_text())
    data["scenarios"][-1]["details"]["engine"] = "tesseract-fast"
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="wrong-engine"):
        verify_variants(root, REVISION, "everyday", "neural")


@pytest.mark.parametrize("failure", ["binary", "missing-choice", "wrong-engine", "over-budget", "failed-gui",
                                      "changed-source", "source-identity", "accuracy-source", "incomplete-accuracy"])
def test_model_release_rejects_partial_or_mismatched_evidence(artifacts, failure):
    root = artifacts()
    folder = root / "OCReady-everyday-multimodal-Linux"
    report = next((folder / "test-output").glob("packaged-neural-*.json"))
    data = json.loads(report.read_text())
    if failure == "binary":
        (folder / "dist/everyday-multimodal/OCReady-everyday-multimodal-linux-x86_64").write_bytes(b"changed")
    elif failure == "missing-choice":
        report.unlink()
    elif failure == "wrong-engine":
        data["scenarios"][0]["details"]["engine"] = "neural:another-pack"
    elif failure == "over-budget":
        data["scenarios"][0]["peak_rss_bytes"] = 1_000_000_000
    elif failure == "failed-gui":
        next(row for row in data["scenarios"] if row["scenario"] == "gui-onefile")["details"]["error"] = "timed out"
    elif failure == "changed-source":
        data["sources_changed_during_run"] = True
    elif failure == "source-identity":
        data["source"] = {"revision": "f" * 40, "dirty": False, "tree_sha256": "b" * 64}
    else:
        path = folder / "test-output/neural-accuracy.json"
        accuracy = json.loads(path.read_text())
        if failure == "accuracy-source":
            accuracy["source"]["dirty"] = True
        else:
            accuracy["cases"].pop()
        path.write_text(json.dumps(accuracy))
    if failure != "missing-choice":
        report.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_variants(root, REVISION, "everyday", "multimodal")


def replace_profile(folder, update):
    path = next(folder.glob("dist/*/build-manifest.json"))
    profile = json.loads(path.read_text())
    update(profile)
    path.write_text(json.dumps(profile))
    for path in (folder / "test-output").glob("packaged-*.json"):
        report = json.loads(path.read_text())
        report["build_profile"] = profile
        path.write_text(json.dumps(report))


@pytest.mark.parametrize("field", ["model_sha256", "projector_sha256", "detector_sha256", "recognizer_sha256", "dictionary_sha256",
                                   "adapter", "languages"])
def test_same_pack_id_cannot_hide_platform_asset_or_capability_difference(artifacts, field):
    root = artifacts()
    def change(profile):
        key = "embedded_neural" if field in {"detector_sha256", "recognizer_sha256", "dictionary_sha256"} else "embedded_models"
        profile[key][0][field] = "6" * 64 if field.endswith("sha256") else "json-cli-v1" if field == "adapter" else "ara"
    replace_profile(root / "OCReady-everyday-multimodal-Windows", change)
    with pytest.raises(ValueError, match="different model assets"):
        verify_variants(root, REVISION, "everyday", "multimodal")


@pytest.mark.parametrize("failure", ["missing-digest", "invalid-digest", "unknown-adapter", "invalid-geometry", "not-bilingual", "duplicate"])
def test_release_rejects_invalid_asset_records_even_when_both_platforms_match(artifacts, failure):
    root = artifacts()
    def change(profile):
        if failure == "missing-digest":
            profile["embedded_models"][0].pop("model_sha256")
        elif failure == "invalid-digest":
            profile["embedded_models"][0]["model_sha256"] = "not a digest"
        elif failure == "unknown-adapter":
            profile["embedded_models"][0]["adapter"] = "unregistered"
        elif failure == "invalid-geometry":
            profile["embedded_neural"][0]["geometry"] = "word"
        elif failure == "not-bilingual":
            profile["embedded_neural"][0]["languages"] = "eng"
        else:
            profile["embedded_models"].append(dict(profile["embedded_models"][0]))
    for folder in root.glob("OCReady-*"):
        replace_profile(folder, change)
    with pytest.raises(ValueError):
        verify_variants(root, REVISION, "everyday", "multimodal")


def test_release_accepts_explicit_default_adapter_and_optional_json_projector(artifacts):
    root = artifacts()
    replace_profile(root / "OCReady-everyday-multimodal-Windows", lambda p: p["embedded_models"][0].update(adapter="llama.cpp"))
    assert len(verify_variants(root, REVISION, "everyday", "multimodal")) == 2
    for folder in root.glob("OCReady-*"):
        replace_profile(folder, lambda p: p["embedded_models"][0].update(adapter="json-cli-v1", projector_sha256=""))
    assert len(verify_variants(root, REVISION, "everyday", "multimodal")) == 2


def test_release_requires_the_same_accuracy_corpus_on_both_platforms(artifacts):
    root = artifacts()
    path = root / "OCReady-everyday-multimodal-Windows/test-output/neural-accuracy.json"
    record = json.loads(path.read_text())
    record["corpus_content_sha256"] = "e" * 64
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="corpus content"):
        verify_variants(root, REVISION, "everyday", "multimodal")


def test_release_accepts_legacy_lf_and_crlf_corpus_checksums(artifacts):
    root = artifacts()
    for path, digest in zip(sorted(root.glob("*/test-output/neural-accuracy.json")), sorted(LEGACY_CORPUS_DIGESTS), strict=True):
        record = json.loads(path.read_text())
        record.pop("corpus_content_sha256")
        record["corpus_sha256"] = digest
        path.write_text(json.dumps(record))
    assert len(verify_variants(root, REVISION, "everyday", "multimodal")) == 2


@pytest.mark.parametrize("failure", ["unknown-legacy-checksum", "changed-text", "duplicate-case", "wrong-engine"])
def test_release_rejects_incompatible_legacy_corpus_or_case_identity(artifacts, failure):
    root = artifacts()
    path = root / "OCReady-everyday-multimodal-Windows/test-output/neural-accuracy.json"
    record = json.loads(path.read_text())
    record.pop("corpus_content_sha256")
    if failure == "unknown-legacy-checksum":
        record["corpus_sha256"] = "e" * 64
    elif failure == "changed-text":
        record["cases"][0]["expected"] += " changed"
    elif failure == "duplicate-case":
        record["cases"][-1] = record["cases"][0]
    else:
        record["cases"][0]["engine"] = "neural:untested-model"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="corpus content"):
        verify_variants(root, REVISION, "everyday", "multimodal")
