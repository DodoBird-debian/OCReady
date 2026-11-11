import os
import sys

import psutil
import pytest

from scripts.startup_probe import launch


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable fixture; native Windows probes are a separate gate")
def test_probe_validates_a_real_child_result_and_cleans_timed_out_descendants(tmp_path):
    script = tmp_path / "child"
    script.write_text(f"#!{sys.executable}\nimport json\nprint(json.dumps({{'sha256': 'expected'}}))\n")
    script.chmod(0o700)
    result = launch(script, "expected")
    assert result["exit_code"] == 0 and result["payload_matches"]
    assert not launch(script, "different")["payload_matches"]
    pid_file = tmp_path / "descendant.pid"
    script.write_text(f"#!{sys.executable}\nimport subprocess, sys, time\nfrom pathlib import Path\n"
                      "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                      f"Path({str(pid_file)!r}).write_text(str(child.pid))\n"
                      "time.sleep(30)\n")
    result = launch(script, "expected", timeout=2)
    assert not result["payload_matches"] and result["exit_code"] is None
    assert "exceeded" in result["error"]
    pid = int(pid_file.read_text())
    try:
        assert psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass
