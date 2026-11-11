import os
import sys

import pytest

from ocready.core.process import run_process
from ocready.core.types import OCRError


def test_worker_failure_retains_actual_exit_code_with_unicode_stderr():
    with pytest.raises(OCRError) as failure:
        run_process([sys.executable, "-c", "import sys; sys.stderr.buffer.write('خطأ worker\\n'.encode('utf-8')); sys.exit(17)"], budget=1_000_000_000)
    assert "exit code 17" in str(failure.value)
    assert "خطأ worker" in str(failure.value)


@pytest.mark.skipif(os.name != "nt", reason="Real Windows process status")
def test_worker_failure_retains_native_windows_status_in_hexadecimal():
    with pytest.raises(OCRError, match="0xC0000005"):
        run_process([sys.executable, "-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000005)"], budget=1_000_000_000)
