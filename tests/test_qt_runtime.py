import json
import shutil
import subprocess
import sys

import pytest

from scripts.qt_runtime import inspect_x11, require_x11


@pytest.mark.skipif(sys.platform != "linux" or not shutil.which("cc"), reason="Native Linux loader check")
def test_loader_preflight_rejects_a_real_missing_shared_library(tmp_path):
    library_source = tmp_path / "dependency.c"
    library_source.write_text("int dependency(void) { return 7; }\n")
    dependency = tmp_path / "libocready-test-dependency.so"
    subprocess.run(["cc", "-shared", "-fPIC", str(library_source), "-o", str(dependency)], check=True)
    plugin_source = tmp_path / "plugin.c"
    plugin_source.write_text("extern int dependency(void); int plugin(void) { return dependency(); }\n")
    plugin = tmp_path / "PySide6/qt-plugins/platforms/libqxcb.so"
    plugin.parent.mkdir(parents=True)
    subprocess.run(["cc", "-shared", "-fPIC", str(plugin_source), "-o", str(plugin),
                    "-L" + str(tmp_path), "-locready-test-dependency", "-Wl,-rpath," + str(tmp_path)], check=True)
    assert inspect_x11(tmp_path)["passed"]
    dependency.unlink()
    output = tmp_path / "diagnostic.json"
    with pytest.raises(RuntimeError, match="libocready-test-dependency.so => not found"):
        require_x11(tmp_path, output=output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["missing"] == [dependency.name]
    assert not report["passed"]
