import json
from pathlib import Path

import pytest

from ocready.core.editions import EDITIONS
from scripts.provenance import file_sha256
from scripts.release_assets import SCENARIOS, prepare_release, verify_artifacts

REVISION = "a" * 40


@pytest.fixture
def artifacts(tmp_path):
    for edition, policy in EDITIONS.items():
        for platform, suffix, runtime_platform in (("Linux", "linux-x86_64", "linux"), ("Windows", "windows-amd64.exe", "win32")):
            root = tmp_path / f"OCReady-{edition}-{platform}"
            binary = root / "dist" / edition / f"OCReady-{edition}-{suffix}"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"synthetic executable")
            digest = file_sha256(binary)
            Path(str(binary) + ".sha256").write_text(f"{digest}  {binary.name}\n")
            profile = {"edition": edition, "methods": ["tesseract-fast", "tesseract-best"],
                       "source": {"revision": REVISION, "dirty": False, "tree_sha256": "b" * 64}}
            (binary.parent / "build-manifest.json").write_text(json.dumps(profile))
            report = {"binary": True, "binary_sha256": digest, "build_profile": profile,
                      "source": profile["source"],
                      "platform": runtime_platform, "sources_changed_during_run": False, "binary_changed_during_run": False,
                      "scenarios": [{"edition": edition, "budget_bytes": policy.budget, "peak_rss_bytes": 1_000_000,
                                     "exit_code": 0, "below_budget": True, "scenario": scenario} for scenario in SCENARIOS]}
            (root / "test-output").mkdir()
            (root / "test-output" / f"packaged-{edition}.json").write_text(json.dumps(report))
    return tmp_path


def test_release_contains_six_verified_binaries_and_checksummed_metadata(artifacts, tmp_path):
    output = tmp_path / "release"
    prepare_release(artifacts, output, REVISION, 123)
    evidence = json.loads((output / "release-evidence.json").read_text())
    assert len(evidence["artifacts"]) == 6
    assert evidence["source_revision"] == REVISION
    for line in (output / "CHECKSUMS.sha256").read_text().splitlines():
        digest, name = line.split()
        assert file_sha256(output / name) == digest
    with pytest.raises(ValueError, match="empty output"):
        prepare_release(artifacts, output, REVISION, 123)


def test_default_release_rejects_a_different_benchmark_controller_source(artifacts):
    report = artifacts / "OCReady-pocket-Linux/test-output/packaged-pocket.json"
    value = json.loads(report.read_text())
    value["source"] = {**value["source"], "revision": "f" * 40}
    report.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="provenance"):
        verify_artifacts(artifacts, REVISION)


@pytest.mark.parametrize("failure", ["binary", "wrong-source", "failed-gui", "over-budget", "changed-during-run"])
def test_release_refuses_unverified_or_mismatched_artifacts(artifacts, failure):
    root = artifacts / "OCReady-pocket-Linux"
    binary = root / "dist" / "pocket" / "OCReady-pocket-linux-x86_64"
    report = root / "test-output" / "packaged-pocket.json"
    data = json.loads(report.read_text())
    if failure == "binary":
        binary.write_bytes(b"different executable")
    elif failure == "wrong-source":
        profile = binary.parent / "build-manifest.json"
        record = json.loads(profile.read_text())
        record["source"]["revision"] = "c" * 40
        profile.write_text(json.dumps(record))
    elif failure == "failed-gui":
        next(row for row in data["scenarios"] if row["scenario"] == "gui-onefile")["exit_code"] = 2
    elif failure == "over-budget":
        data["scenarios"][0]["peak_rss_bytes"] = EDITIONS["pocket"].budget
    else:
        data["sources_changed_during_run"] = True
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_artifacts(artifacts, REVISION)
