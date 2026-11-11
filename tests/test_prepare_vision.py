import hashlib
import io
import tarfile
import zipfile

import pytest

from scripts.prepare_vision import extract_runner, fetch, quantize_model


def test_derived_weight_cache_and_mismatch_never_publish_unverified_output(tmp_path, monkeypatch):
    content = b"GGUFderived"
    derived = {"file": "compact.gguf", "input": "original.gguf", "quantization": "Q4_0",
               "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    target = tmp_path / derived["file"]
    target.write_bytes(content)
    assert quantize_model(derived, tmp_path, None) == target
    target.unlink()
    quantizer = tmp_path / "llama-quantize"
    quantizer.write_bytes(b"tool")
    def invalid_output(command, **_kwargs):
        from pathlib import Path
        Path(command[-2]).write_bytes(b"wrong model")
    monkeypatch.setattr("scripts.prepare_vision.subprocess.run", invalid_output)
    with pytest.raises(RuntimeError, match="differ from the locked"):
        quantize_model(derived, tmp_path, quantizer)
    assert not target.exists() and not list(tmp_path.glob(".vision-quantize-*"))


def test_locked_download_does_not_publish_corrupt_or_oversized_data(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"corrupt")
    target = tmp_path / "models/model.gguf"
    record = {"url": source.as_uri(), "bytes": 4, "sha256": hashlib.sha256(b"GGUF").hexdigest()}
    with pytest.raises(RuntimeError, match="exceeds"):
        fetch(record, target)
    assert not target.exists()
    assert not list(target.parent.glob(".vision-download-*"))
    source.write_bytes(b"nope")
    with pytest.raises(RuntimeError, match="differs"):
        fetch(record, target)
    source.write_bytes(b"GGUF")
    fetch(record, target)
    source.unlink()
    fetch(record, target)  # A verified cache does not require the network.
    assert target.read_bytes() == b"GGUF"


@pytest.mark.parametrize("kind", ["zip", "tar"])
def test_cpu_archives_preserve_runtime_and_reject_escaping_paths(tmp_path, kind):
    path = tmp_path / ("runtime." + kind)
    if kind == "zip":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("bin/llama-mtmd-cli.exe", b"runner")
            archive.writestr("bin/ggml.dll", b"library")
    else:
        with tarfile.open(path, "w") as archive:
            for name, content in [("bin/llama-mtmd-cli", b"runner"), ("bin/libggml.so.1", b"library")]:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            alias = tarfile.TarInfo("bin/libggml.so")
            alias.type, alias.linkname = tarfile.SYMTYPE, "libggml.so.1"
            archive.addfile(alias)
    runner = extract_runner(path, tmp_path / "out")
    assert runner.read_bytes() == b"runner"
    if kind == "tar":
        assert (runner.parent / "libggml.so").read_bytes() == b"library"
    if kind == "zip":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../outside", b"escape")
    else:
        with tarfile.open(path, "w") as archive:
            alias = tarfile.TarInfo("escape")
            alias.type, alias.linkname = tarfile.SYMTYPE, "../outside"
            archive.addfile(alias)
    with pytest.raises(ValueError, match="Unsafe"):
        extract_runner(path, tmp_path / "bad")
    assert not (tmp_path / "outside").exists()
