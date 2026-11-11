"""Run portable-binary checks without borrowing a developer's runtime setup."""
import os
import sys
from collections.abc import Mapping
from pathlib import Path

DEVELOPMENT_OVERRIDES = frozenset({
    "PATH", "OCREADY_RUNTIME", "OCREADY_TESSERACT", "TESSDATA_PREFIX", "PYTHONPATH", "PYTHONHOME",
    "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "PYTHONIOENCODING", "PYTHONUTF8",
    "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_PLATFORM", "QT_DEBUG_PLUGINS",
    "QML_IMPORT_PATH", "QML2_IMPORT_PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH",
})


def gui_test_platform() -> str:
    platform = os.environ.get("OCREADY_GUI_TEST_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
    if platform not in {"windows", "xcb", "wayland", "offscreen"}:
        raise ValueError("Choose windows, xcb, wayland or offscreen for the GUI test platform.")
    return platform


def execution_policy(isolated: bool = True) -> dict:
    return {"policy": "isolated-runtime-v1" if isolated else "inherited-source-environment",
            "path_scope": "OS system directories" if isolated else "inherited",
            "unicode_runtime_temp": True, "private_configuration": True, "development_overrides_removed": isolated,
            "gui_platform": gui_test_platform()}


def runtime_test_environment(temp_root: Path, *, isolated: bool = True,
                             base: Mapping[str, str] | None = None, platform: str | None = None) -> dict[str, str]:
    original = dict(os.environ if base is None else base)
    env = {key: value for key, value in original.items()
           if key.upper() not in {"TEMP", "TMP", "TMPDIR", "XDG_CONFIG_HOME", "APPDATA"}
           and (not isolated or key.upper() not in DEVELOPMENT_OVERRIDES)}
    if isolated:
        if (platform or sys.platform) == "win32":
            folded = {key.upper(): value for key, value in original.items()}
            root = folded.get("SYSTEMROOT") or folded.get("WINDIR")
            if not root:
                raise ValueError("Windows isolation needs the operating system's SystemRoot directory.")
            root = root.rstrip("\\/")
            env["PATH"] = root + r"\System32;" + root
        else:
            env["PATH"] = os.defpath
    temp_root = temp_root.resolve()
    temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    env.update({name: str(temp_root) for name in ("TEMP", "TMP", "TMPDIR")})
    config = temp_root.parent / "config"
    config.mkdir(parents=True, exist_ok=True, mode=0o700)
    env.update({name: str(config) for name in ("XDG_CONFIG_HOME", "APPDATA")})
    return env
