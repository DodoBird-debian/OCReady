"""Small, path-free source records for build and benchmark artifacts."""
import hashlib
import subprocess
from pathlib import Path

SOURCE_PATHS = ("ocready", "scripts", "native", "tests", "assets", "docs", ".github",
                "launch.py", "pyproject.toml", "uv.lock", "README.md", "LICENSE")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(root: Path) -> dict:
    files = []
    for name in SOURCE_PATHS:
        path = root / name
        files.extend(path.rglob("*") if path.is_dir() else [path])
    digest = hashlib.sha256()
    for path in sorted(files):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(file_sha256(path).encode("ascii") + b"\0")
    revision, dirty = "unknown", None
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL,
                                           text=True, timeout=10).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"],
                                            cwd=root, stderr=subprocess.DEVNULL, timeout=10))
    except (OSError, subprocess.SubprocessError):
        pass
    return {"revision": revision, "dirty": dirty, "tree_sha256": digest.hexdigest()}


def require_unchanged(root: Path, original: dict) -> None:
    current = source_record(root)
    if current["revision"] != original["revision"] or current["tree_sha256"] != original["tree_sha256"]:
        raise RuntimeError("Project sources changed during compilation. Rebuild before distributing this artifact.")


def included_runtime_manifest(runtime: Path, names: set[str]) -> dict:
    import json
    manifest = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))
    included = {name: expected for name, expected in manifest.get("files", {}).items() if name in names}
    for name, expected in included.items():
        if file_sha256(runtime / name) != expected:
            raise RuntimeError(f"Prepared runtime changed: {name}. Run prepare_runtime.py again.")
    manifest["files"] = included
    if not any(name in names for name in ("bin/tesseract", "bin/tesseract.exe")):
        manifest.pop("version", None)
    if "bin/ocready-exec-gate" not in names:
        manifest.pop("exec_gate_protocol", None)
    return manifest
