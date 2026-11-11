import os
import sys

import pytest

from ocready.core.process import WorkerFailed, run_process
from ocready.core.types import OCRError


def test_worker_failure_retains_actual_exit_code_with_unicode_stderr():
    with pytest.raises(OCRError) as failure:
        run_process([sys.executable, "-c", "import sys; sys.stderr.buffer.write('خطأ worker\\n'.encode('utf-8')); sys.exit(17)"], budget=1_000_000_000)
    assert "exit code 17" in str(failure.value)
    assert "خطأ worker" in str(failure.value)


def test_gpu_failure_cause_survives_a_long_diagnostic_tail():
    code = "import sys; sys.stderr.buffer.write(('CUDA error: unsupported PTX toolchain\\n'+'x'*20000+' خطأ').encode('utf-8')); sys.exit(23)"
    with pytest.raises(WorkerFailed) as failure:
        run_process([sys.executable, "-c", code], budget=1_000_000_000)
    error = failure.value
    assert error.exit_code == 23 and error.cuda_failure
    assert "CUDA error: unsupported PTX" in str(error) and str(error).endswith(" خطأ")
    assert len(str(error)) < 2000


@pytest.mark.skipif(os.name != "nt", reason="Real Windows process status")
def test_worker_failure_retains_native_windows_status_in_hexadecimal():
    with pytest.raises(OCRError, match="0xC0000005"):
        run_process([sys.executable, "-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000005)"], budget=1_000_000_000)
