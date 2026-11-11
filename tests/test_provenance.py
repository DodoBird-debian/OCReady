import hashlib
import json

import pytest

from scripts.provenance import included_runtime_manifest, require_unchanged, source_record


def test_source_record_detects_changed_sources_but_ignores_build_outputs(tmp_path):
    (tmp_path / "ocready").mkdir()
    source = tmp_path / "ocready" / "app.py"
    source.write_text("version = 1")
    original = source_record(tmp_path)
    assert original["revision"] == "unknown"
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "binary").write_bytes(b"build result")
    require_unchanged(tmp_path, original)
    source.write_text("version = 2")
    with pytest.raises(RuntimeError, match="changed during compilation"):
        require_unchanged(tmp_path, original)


def test_runtime_manifest_lists_only_bundled_files_and_rejects_stale_hashes(tmp_path):
    files = {}
    for name in ("bin/tesseract", "bin/ocready-exec-gate", "tessdata/fast/ara", "tessdata/best/ara"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({"version": "tesseract 5", "exec_gate_protocol": 2, "files": files}))
    names = {"bin/tesseract", "bin/ocready-exec-gate", "tessdata/fast/ara"}
    assert set(included_runtime_manifest(tmp_path, names)["files"]) == names
    vision = included_runtime_manifest(tmp_path, {"bin/ocready-exec-gate"})
    assert "version" not in vision
    assert vision["exec_gate_protocol"] == 2
    assert "exec_gate_protocol" not in included_runtime_manifest(tmp_path, {"bin/tesseract"})
    (tmp_path / "bin" / "tesseract").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="Prepared runtime changed"):
        included_runtime_manifest(tmp_path, names)
