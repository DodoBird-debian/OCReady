import json
import os
import subprocess
import sys

import pytest

from ocready.core import paths
from ocready.engines import tesseract
from scripts.packaged_environment import runtime_test_environment
from scripts.release_assets import verify_execution_environment


def test_packaged_tesseract_cannot_silently_borrow_system_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    for name in ("OCREADY_RUNTIME", "OCREADY_TESSERACT", "TESSDATA_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    system_engine = tmp_path / "system-engine"
    system_engine.write_bytes(b"installed separately")
    system_data = tmp_path / "system-data"
    system_data.mkdir()
    for name in ("ara", "eng"):
        (system_data / f"{name}.traineddata").write_bytes(b"external language data")
    monkeypatch.setattr(tesseract.shutil, "which", lambda _: str(system_engine))
    monkeypatch.setattr(tesseract, "SYSTEM_DATA_DIRS", (system_data,))
    assert not paths.is_packaged()
    assert tesseract.executable() == system_engine and tesseract.data_dir() == system_data
    (tmp_path / "build-manifest.json").write_text(json.dumps({"methods": ["tesseract-fast"]}))
    assert paths.is_packaged()
    assert tesseract.executable() is None and tesseract.data_dir() is None
    assert not tesseract.readiness()[0]
    assert "built-in" in tesseract.readiness()[1]
    assert "does not include Precision" in tesseract.readiness("best")[1]
    # Deliberately selected external assets remain supported.
    monkeypatch.setenv("OCREADY_TESSERACT", str(system_engine))
    monkeypatch.setenv("TESSDATA_PREFIX", str(system_data))
    assert tesseract.readiness()[0]


def test_isolated_worker_uses_unicode_temp_without_python_or_plugin_overrides(tmp_path):
    base = {**os.environ, "PYTHONHOME": "missing-python-home", "PYTHONPATH": "missing-modules",
            "VIRTUAL_ENV": "developer-environment", "QT_PLUGIN_PATH": "developer-plugins",
            "OCREADY_RUNTIME": "developer-runtime", "LD_LIBRARY_PATH": "developer-libraries"}
    directory = tmp_path / "تشغيل آمن"
    env = runtime_test_environment(directory, base=base)
    script = ("import json, os, tempfile\nfrom pathlib import Path\n"
              "path = Path(tempfile.gettempdir()) / 'نص.txt'\n"
              "path.write_text('مرحبا ٢٥٠٠', encoding='utf-8')\n"
              "print(json.dumps({'text':path.read_text(encoding='utf-8'), 'temp':tempfile.gettempdir(),"
              "'pythonhome':os.getenv('PYTHONHOME'), 'plugin':os.getenv('QT_PLUGIN_PATH'),"
              "'runtime':os.getenv('OCREADY_RUNTIME')}))\n")
    result = subprocess.run([sys.executable, "-c", script], env=env, check=True, capture_output=True, text=True)
    record = json.loads(result.stdout)
    assert record["text"] == "مرحبا ٢٥٠٠" and record["temp"] == str(directory.resolve())
    assert record["pythonhome"] is record["plugin"] is record["runtime"] is None
    assert "developer-environment" not in env["PATH"]


@pytest.mark.parametrize("root_key", ["SystemRoot", "SYSTEMROOT", "windir"])
def test_windows_isolation_preserves_system_dll_search_without_developer_path(tmp_path, root_key):
    env = runtime_test_environment(tmp_path / "لغة", platform="win32",
                                   base={root_key: r"D:\Windows", "Path": r"D:\Developer\Python;D:\Developer\OCR",
                                         "pythonpath": "extra-modules", "APPDATA": "user-config"})
    assert env["PATH"] == r"D:\Windows\System32;D:\Windows"
    assert "Path" not in env and "pythonpath" not in env
    assert env["APPDATA"] == str((tmp_path / "config").resolve())
    assert env["XDG_CONFIG_HOME"] == env["APPDATA"]


def test_windows_isolation_refuses_an_unknown_os_root(tmp_path):
    with pytest.raises(ValueError, match="SystemRoot"):
        runtime_test_environment(tmp_path, base={}, platform="win32")


@pytest.mark.parametrize("runtime,gui", [("linux", "xcb"), ("linux", "wayland"), ("win32", "windows")])
def test_release_requires_actual_native_gui_and_isolation_for_new_builds(runtime, gui):
    profile = {"validation_policy": {"portable_runtime_environment": 1, "native_gui_backend": True, "unicode_paths": True}}
    environment = {"policy": "isolated-runtime-v1", "path_scope": "OS system directories", "unicode_runtime_temp": True,
                   "private_configuration": True, "development_overrides_removed": True, "gui_platform": gui}
    report = {"execution_environment": environment, "scenarios": [{"scenario": "gui-onefile", "details": {"qt_platform": gui}}]}
    verify_execution_environment(report, profile, runtime)
    report["scenarios"][0]["details"]["qt_platform"] = "offscreen"
    with pytest.raises(ValueError, match="windowing backend"):
        verify_execution_environment(report, profile, runtime)
    report["scenarios"][0]["details"]["qt_platform"] = gui
    environment["development_overrides_removed"] = False
    with pytest.raises(ValueError, match="isolated runtimes"):
        verify_execution_environment(report, profile, runtime)
    with pytest.raises(ValueError, match="isolated runtimes"):
        verify_execution_environment({}, profile, runtime)
    profile["validation_policy"]["portable_runtime_environment"] = True
    with pytest.raises(ValueError, match="Unsupported"):
        verify_execution_environment(report, profile, runtime)
    # Existing artifacts retain their original scope instead of gaining a claim.
    verify_execution_environment({}, {}, runtime)
