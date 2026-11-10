"""Collect local Tesseract + pinned language data; never needs root on Debian.

Windows: install Tesseract with Chocolatey first (choco install tesseract -y).
Then run this script. Build inputs remain outside git in runtime/.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
REVISIONS = {"fast": "87416418657359cb625c412a48b6e1d6d41c29bd", "best": "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"}
LOCK_PATH = ROOT / "assets" / "language-lock.json"


def download(url: str, path: Path, expected: str | None) -> str:
    if path.exists() and expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return expected
    with urllib.request.urlopen(url, timeout=60) as response:
        blob = response.read(25_000_000)
    digest = hashlib.sha256(blob).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f"Checksum mismatch for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_bytes(blob)
    temporary.replace(path)
    return digest


def linux_runtime() -> Path:
    program = shutil.which("tesseract")
    if program:
        return Path(program)
    existing = RUNTIME / "debian" / "usr" / "bin" / "tesseract"
    if existing.exists():
        return existing
    if not shutil.which("apt-get") or not shutil.which("dpkg-deb"):
        raise RuntimeError("Install Tesseract first, or prepare on Debian/Ubuntu with apt-get available.")
    with tempfile.TemporaryDirectory(prefix="ocready-packages-") as directory:
        depends = subprocess.check_output(["apt-cache", "depends", "libtesseract5"], text=True)
        lept = "libleptonica6" if "libleptonica6" in depends else "liblept5"
        subprocess.run(["apt-get", "download", "tesseract-ocr", "libtesseract5", lept], cwd=directory, check=True)
        extracted = RUNTIME / "debian"
        extracted.mkdir(parents=True, exist_ok=True)
        for package in Path(directory).glob("*.deb"):
            subprocess.run(["dpkg-deb", "-x", str(package), str(extracted)], check=True)
    return existing


def collect_linux(program: Path) -> None:
    target = RUNTIME / "bin" / "tesseract"
    if program.resolve() != target.resolve():
        shutil.copy2(program, target)
    target.chmod(0o755)
    for directory in (RUNTIME / "debian" / "usr" / "lib").glob("*-linux-gnu"):
        for library in directory.glob("*.so*"):
            shutil.copy2(library.resolve(), RUNTIME / "lib" / library.name)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(RUNTIME / "lib")
    dependencies = subprocess.check_output(["ldd", str(target)], text=True, env=env)
    if "not found" in dependencies:
        raise RuntimeError("Missing OCR dependencies:\n" + dependencies)
    # Never bundle the OS loader or core glibc. Other dependencies travel with the child executable.
    excluded = {"libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0", "librt.so.1", "libresolv.so.2"}
    for value in re.findall(r"=> (/\S+)", dependencies):
        library = Path(value)
        if library.name not in excluded and library.parent.resolve() != (RUNTIME / "lib").resolve():
            shutil.copy2(library.resolve(), RUNTIME / "lib" / library.name)
    notices = RUNTIME / "notices"
    for folder in [Path("/usr/share/doc"), RUNTIME / "debian" / "usr" / "share" / "doc"]:
        for package in ("tesseract-ocr", "libtesseract5", "libleptonica6", "liblept5"):
            copyright_file = folder / package / "copyright"
            if copyright_file.exists():
                shutil.copy2(copyright_file, notices / f"{package}-copyright.txt")


def collect_windows() -> Path:
    candidates = [shutil.which("tesseract"), r"C:\Program Files\Tesseract-OCR\tesseract.exe"]
    source = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
    if source is None:
        raise RuntimeError("Install Tesseract first: choco install tesseract -y")
    for path in [source, *source.parent.glob("*.dll")]:
        shutil.copy2(path, RUNTIME / "bin" / path.name)
    for pattern in ("LICENSE*", "COPYING*", "AUTHORS*", "*copyright*"):
        for path in source.parent.glob(pattern):
            if path.is_file():
                shutil.copy2(path, RUNTIME / "notices" / path.name)
    return RUNTIME / "bin" / "tesseract.exe"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--best", action="store_true", help="Also prepare best Arabic/English models")
    parser.add_argument("--update-lock", action="store_true", help="Maintainer: explicitly accept hashes for pinned assets")
    args = parser.parse_args()
    for name in ("bin", "lib", "notices"):
        (RUNTIME / name).mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        program = collect_windows()
    else:
        collect_linux(linux_runtime())
        program = RUNTIME / "bin" / "tesseract"
    lock = json.loads(LOCK_PATH.read_text()) if LOCK_PATH.exists() else {}
    for quality in (["fast", "best"] if args.best else ["fast"]):
        for language in ("ara", "eng"):
            key = f"{quality}/{language}"
            url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_{quality}/{REVISIONS[quality]}/{language}.traineddata"
            expected = lock.get(key, {}).get("sha256")
            if not expected and not args.update_lock:
                raise RuntimeError(f"Missing pinned hash for {key}; maintainer must review --update-lock first")
            print(f"Preparing {key}…", flush=True)
            digest = download(url, RUNTIME / "tessdata" / quality / f"{language}.traineddata", expected)
            lock[key] = {"url": url, "sha256": digest}
        download(f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_{quality}/{REVISIONS[quality]}/LICENSE",
                 RUNTIME / "notices" / f"tessdata_{quality}-LICENSE.txt", None)
    if args.update_lock:
        LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n")
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(RUNTIME / "lib")
    version = subprocess.check_output([str(program), "--version"], env=env, text=True).splitlines()[0]
    files = {str(p.relative_to(RUNTIME)): hashlib.sha256(p.read_bytes()).hexdigest()
             for base in ("bin", "lib", "tessdata", "notices") for p in (RUNTIME / base).rglob("*") if p.is_file()}
    (RUNTIME / "manifest.json").write_text(json.dumps({"version": version, "platform": sys.platform, "files": files}, indent=2) + "\n")
    print(f"Ready: {version}; {len(files)} runtime files")


if __name__ == "__main__":
    main()
