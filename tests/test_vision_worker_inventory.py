import json
import os

import pytest

from scripts.provenance import file_sha256
from scripts.verify_vision_worker import verify_worker


@pytest.fixture
def worker(tmp_path):
    source, folder = tmp_path / "source", tmp_path / "worker"
    inputs = {"entrypoint_sha256": "native/vision_bridge.py", "builder_sha256": "scripts/build_vision_bridge.py",
              "backend_errors_sha256": "ocready/core/backend_errors.py", "backend_probe_sha256": "ocready/core/backend_probe.py"}
    for relative in inputs.values():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"source")
    suffix = ".exe" if os.name == "nt" else ""
    for name in ("ocready-vision-bridge" + suffix, "llama/llama-mtmd-cli" + suffix, "runtime.dll"):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"runtime")
    metadata = {"protocol": 1, "adapter": "json-cli-v1", "source": {"dirty": False}, "python": "3.12.test",
                **{key: file_sha256(source / relative) for key, relative in inputs.items()},
                "files": {p.relative_to(folder).as_posix(): file_sha256(p) for p in folder.rglob("*") if p.is_file()},
                "native_runner_sha256": file_sha256(folder / ("llama/llama-mtmd-cli" + suffix))}
    (folder / "vision-build.json").write_text(json.dumps(metadata))
    return folder, source


@pytest.mark.parametrize("change", ["none", "undeclared-library", "tampered-library", "parser", "native-identity", "escaping-path"])
def test_compiled_vision_identity_rejects_stale_or_undeclared_runtime(worker, change):
    folder, source = worker
    marker = folder / "vision-build.json"
    data = json.loads(marker.read_text())
    if change == "undeclared-library":
        (folder / "unexpected-cuda.dll").write_bytes(b"library")
    elif change == "tampered-library":
        (folder / "runtime.dll").write_bytes(b"changed")
    elif change == "parser":
        (source / "ocready/core/backend_probe.py").write_bytes(b"changed")
    elif change == "native-identity":
        data["native_runner_sha256"] = "0" * 64
    elif change == "escaping-path":
        data["files"]["../outside"] = "0" * 64
    marker.write_text(json.dumps(data))
    if change == "none":
        assert verify_worker(folder, source_root=source, python_version="3.12.test") == data
    else:
        with pytest.raises(ValueError):
            verify_worker(folder, source_root=source, python_version="3.12.test")
