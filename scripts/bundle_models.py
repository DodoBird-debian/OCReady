"""Write selected local VLM packs into a onefile runtime archive."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

from ocready.core.models import ModelPack
from ocready.core.neural_packs import NeuralPack


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_pack(archive: tarfile.TarFile, pack: ModelPack) -> dict:
    pack.validate()
    prefix = Path("vision") / pack.id
    values = pack.to_dict()
    for key in ("model", "projector"):
        if not getattr(pack, key):
            continue
        source = Path(getattr(pack, key)).expanduser().resolve()
        name = key + (".gguf" if pack.adapter == "llama.cpp" else source.suffix or ".bin")
        archive.add(source, arcname=(prefix / name).as_posix(), recursive=False)
        values[key] = name
    for key in ("runner", "cuda_runner"):
        if not getattr(pack, key):
            continue
        source = Path(getattr(pack, key)).expanduser().resolve()
        folder = "cpu" if key == "runner" else "cuda"
        files = {source, *source.parent.glob("*.dll"), *source.parent.glob("*.so*")}
        libdir = source.parent.parent / "lib"
        if libdir.is_dir():
            files.update(libdir.glob("*.so*"))
        for file in sorted(files):
            if file.is_file():
                # Tar hard links preserve shared-library aliases without duplicate bytes.
                archive.add(file.resolve(), arcname=(prefix / folder / file.name).as_posix(), recursive=False)
        values[key] = (Path(folder) / source.name).as_posix()
        for pattern in ("LICENSE*", "COPYING*", "NOTICE*", "*license*"):
            for notice in source.parent.glob(pattern):
                if notice.is_file():
                    archive.add(notice, arcname=(prefix / "notices" / folder / notice.name).as_posix(), recursive=False)
        for notice in (source.parent / "notices").glob("**/*"):
            if notice.is_file():
                archive.add(notice, arcname=(prefix / "notices" / folder / notice.relative_to(source.parent / "notices")).as_posix(), recursive=False)
    for pattern in ("LICENSE*", "NOTICE*", "README*", "modelcard*"):
        for notice in Path(pack.model).parent.glob(pattern):
            if notice.is_file():
                archive.add(notice, arcname=(prefix / "notices" / "model" / notice.name).as_posix(), recursive=False)
    values["bundled"] = True
    blob = json.dumps(values, ensure_ascii=False, indent=2).encode("utf-8")
    info = tarfile.TarInfo((prefix / "pack.json").as_posix())
    info.size, info.mode = len(blob), 0o644
    archive.addfile(info, io.BytesIO(blob))
    return {"id": pack.id, "name": pack.name, "source": pack.source, "license": pack.license,
            "languages": pack.languages, "adapter": pack.adapter, "model_sha256": file_digest(Path(pack.model)),
            "projector_sha256": file_digest(Path(pack.projector)) if pack.projector else ""}


def bundle_neural_pack(archive: tarfile.TarFile, pack: NeuralPack) -> dict:
    pack.validate()
    prefix = Path("neural") / pack.id
    values = pack.to_dict()
    hashes = {}
    for key, name in (("detector", "detector.onnx"), ("recognizer", "recognizer.onnx"), ("dictionary", "dictionary.txt")):
        source = Path(getattr(pack, key)).expanduser().resolve()
        archive.add(source, arcname=(prefix / name).as_posix(), recursive=False)
        values[key] = name
        hashes[key + "_sha256"] = file_digest(source)
    for key in ("runner", "cuda_runner"):
        if not getattr(pack, key):
            continue
        runner = Path(getattr(pack, key)).expanduser().resolve()
        folder = "cpu" if key == "runner" else "cuda"
        # Embed the declared standalone distribution, not arbitrary files a user
        # might have stored beside an executable in e.g. /usr/bin or Downloads.
        marker = runner.parent / "neural-build.json"
        if not marker.is_file() or marker.stat().st_size > 1_000_000:
            raise ValueError("Embedding neural OCR requires the standalone worker directory produced by build_neural_runner.py.")
        metadata = json.loads(marker.read_text(encoding="utf-8"))
        files = metadata.get("files", {})
        if metadata.get("protocol") != 1 or not isinstance(files, dict) or runner.name not in files:
            raise ValueError("The neural worker distribution manifest is invalid.")
        for relative, digest in sorted(files.items()):
            path = Path(relative)
            source = runner.parent / path
            if path.is_absolute() or ".." in path.parts or not source.resolve().is_relative_to(runner.parent):
                raise ValueError("The neural worker distribution contains an escaping path.")
            if not source.is_file() or file_digest(source) != digest:
                raise ValueError(f"The neural worker distribution changed: {relative}")
            archive.add(source.resolve(), arcname=(prefix / folder / path).as_posix(), recursive=False)
        archive.add(marker, arcname=(prefix / folder / marker.name).as_posix(), recursive=False)
        values[key] = (Path(folder) / runner.name).as_posix()
    for pattern in ("*LICENSE*", "NOTICE*", "README*", "*-inference.yml"):
        for notice in Path(pack.recognizer).parent.glob(pattern):
            if notice.is_file():
                archive.add(notice, arcname=(prefix / "notices/model" / notice.name).as_posix(), recursive=False)
    values["bundled"] = True
    blob = json.dumps(values, ensure_ascii=False, indent=2).encode("utf-8")
    info = tarfile.TarInfo((prefix / "pack.json").as_posix())
    info.size, info.mode = len(blob), 0o644
    archive.addfile(info, io.BytesIO(blob))
    return {"id": pack.id, "name": pack.name, "source": pack.source, "license": pack.license,
            "languages": pack.languages, "geometry": "line", **hashes}
