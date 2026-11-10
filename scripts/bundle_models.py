"""Write selected local VLM packs into a onefile runtime archive."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

from ocready.core.models import ModelPack


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
        source = Path(getattr(pack, key)).expanduser().resolve()
        name = key + ".gguf"
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
            "languages": pack.languages, "model_sha256": file_digest(Path(pack.model)),
            "projector_sha256": file_digest(Path(pack.projector))}
