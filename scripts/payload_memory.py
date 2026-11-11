"""Build with an isolated, version-checked Nuitka bootstrap overlay."""
import importlib.metadata
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from scripts.provenance import file_sha256

SUPPORTED_NUITKA = "4.3.5"
INCLUDE_MARKER = "#include <wchar.h>\n"
CALL_MARKER = "    // We are done with the unpacking now."


def patch_bootstrap(source: str, header: str) -> str:
    if source.count(INCLUDE_MARKER) != 1 or source.count(CALL_MARKER) != 1:
        raise RuntimeError("The Nuitka bootstrap layout changed. Review the payload patch or use --no-payload-trim.")
    if "ocready_release_payload_pages" in source:
        raise RuntimeError("The Nuitka bootstrap is already patched unexpectedly.")
    source = source.replace(INCLUDE_MARKER, INCLUDE_MARKER + "\n" + header + "\n")
    return source.replace(CALL_MARKER, "    ocready_release_payload_pages(payload_data, payload_size);\n\n" + CALL_MARKER)


@contextmanager
def compiler_overlay(stage: Path, *, enabled: bool = True):
    """Never modify the installed compiler, including on failure/interruption."""
    if not enabled:
        yield None, {"enabled": False}
        return
    version = importlib.metadata.version("Nuitka")
    if version != SUPPORTED_NUITKA:
        raise RuntimeError(f"Payload trimming is verified for Nuitka {SUPPORTED_NUITKA}; found {version}. Use the lockfile or --no-payload-trim.")
    import nuitka
    package = Path(nuitka.__file__).parent
    relative = Path("build/static_src/OnefileBootstrap.c")
    original = package / relative
    header = Path(__file__).resolve().parents[1] / "native/payload_memory.h"
    metadata = {"enabled": True, "nuitka": version, "strategy": "drop-unused-launcher-pages-v1",
                "original_bootstrap_sha256": file_sha256(original), "helper_sha256": file_sha256(header)}
    stage.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compiler-", dir=stage) as temporary:
        overlay = Path(temporary)
        shutil.copytree(package, overlay / "nuitka", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        bootstrap = overlay / "nuitka" / relative
        bootstrap.write_text(patch_bootstrap(original.read_text(encoding="utf-8"), header.read_text(encoding="utf-8")), encoding="utf-8")
        metadata["patched_bootstrap_sha256"] = file_sha256(bootstrap)
        yield overlay, metadata


def overlay_environment(env: dict[str, str], overlay: Path | None) -> dict[str, str]:
    result = env.copy()
    if overlay:
        result["PYTHONPATH"] = str(overlay) + (os.pathsep + result["PYTHONPATH"] if result.get("PYTHONPATH") else "")
    return result
