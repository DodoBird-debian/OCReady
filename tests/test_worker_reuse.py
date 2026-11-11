import json
import os

import pytest

from scripts.provenance import file_sha256
from scripts.verify_neural_worker import verify_worker


@pytest.fixture
def worker(tmp_path):
    source = tmp_path / "source"
    for relative in ("native/neural_runner.py", "scripts/build_neural_runner.py"):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source input")
    folder = tmp_path / "worker"
    folder.mkdir()
    name = "ocready-neural-runner.exe" if os.name == "nt" else "ocready-neural-runner"
    (folder / name).write_bytes(b"compiled worker")
    (folder / "runtime.dll").write_bytes(b"library")
    metadata = {"protocol": 1, "source": {"dirty": False}, "dependencies": {"runtime": "1"}, "python": "3.12.16",
                "entrypoint_sha256": file_sha256(source / "native/neural_runner.py"),
                "builder_sha256": file_sha256(source / "scripts/build_neural_runner.py"),
                "files": {p.name: file_sha256(p) for p in folder.iterdir()}}
    marker = folder / "neural-build.json"
    marker.write_text(json.dumps(metadata))
    return folder, source, marker


def check(worker):
    folder, source, _marker = worker
    verify_worker(folder, source_root=source, dependencies={"runtime": "1"}, python_version="3.12.16")


def test_reusable_worker_matches_current_sources_dependencies_and_contents(worker):
    check(worker)
    folder, _source, _marker = worker
    (folder / "runtime.dll").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="inventory changed"):
        check(worker)


@pytest.mark.parametrize("change", ["entrypoint", "builder", "dependency", "python", "protocol", "unclean", "escape"])
def test_worker_cache_cannot_hide_incompatible_inputs(worker, change):
    _folder, source, marker = worker
    metadata = json.loads(marker.read_text())
    if change in {"entrypoint", "builder"}:
        path = source / ("native/neural_runner.py" if change == "entrypoint" else "scripts/build_neural_runner.py")
        path.write_text("changed source")
    elif change == "dependency":
        metadata["dependencies"]["runtime"] = "2"
    elif change == "python":
        metadata["python"] = "3.13.1"
    elif change == "protocol":
        metadata["protocol"] = True
    elif change == "unclean":
        metadata["source"]["dirty"] = True
    else:
        metadata["files"]["../outside"] = "a" * 64
    marker.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        check(worker)
