import os
import sys
import time

import psutil
import pytest

from ocready.core.containment import linux_gate
from ocready.core.memory import tree_rss
from ocready.core.process import run_process
from ocready.core.types import BudgetExceeded


def require_worker_limits():
    if os.name != "nt" and linux_gate() is None:
        pytest.skip("This machine has no delegated Linux desktop bus / prepared worker gate")


def test_native_worker_limit_is_installed_before_the_engine_runs():
    require_worker_limits()
    result = run_process([sys.executable, "-c", "print('worker ready')"], budget=tree_rss() + 160_000_000)
    assert result.stdout.strip() == "worker ready"
    assert result.containment == ("windows-job" if os.name == "nt" else "cgroup-v2")
    assert 0 < result.worker_limit < 160_000_000


def test_native_worker_limit_blocks_a_large_allocation():
    require_worker_limits()
    code = "try:\n data = bytearray(320_000_000)\n print('unbounded')\nexcept MemoryError:\n print('allocation limited')"
    try:
        result = run_process([sys.executable, "-c", code], budget=tree_rss() + 112_000_000, timeout=10)
    except BudgetExceeded as error:
        assert os.name != "nt"
        assert "operating system" in str(error)
    else:
        assert os.name == "nt"
        assert result.containment == "windows-job"
        assert result.stdout.strip() == "allocation limited"


def test_worker_limit_cleans_up_grandchildren_after_parent_exit():
    require_worker_limits()
    code = "import subprocess,sys; child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); print(child.pid,flush=True)"
    result = run_process([sys.executable, "-c", code], budget=tree_rss() + 160_000_000)
    assert result.containment in {"cgroup-v2", "windows-job"}
    pid = int(result.stdout.strip())
    deadline = time.monotonic() + 2
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(.01)
    assert not psutil.pid_exists(pid), "An OCR grandchild survived job/scope disposal"
