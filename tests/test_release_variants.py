import json
from pathlib import Path

import pytest

from scripts.provenance import file_sha256
from scripts.release_assets import SCENARIOS
from scripts.release_variants import prepare_release, verify_variants
from scripts.smoke_binary import embedded_selections

REVISION = "a" * 40


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
                       "embedded_models": [] if variant == "neural" else [{"id": "small"}], "embedded_neural": [{"id": "bilingual"}]}
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
            accuracy = {"source": source, "sources_changed_during_run": False, "corpus_sha256": "d" * 64,
                        "summaries": {"neural": {"completed": 11, "errors": 0, "skipped": 0, "cer": .04, "wer": .08}},
                        "cases": [{"status": "ok", "method": "neural"} for _ in range(11)]}
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
