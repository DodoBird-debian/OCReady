import sys

from scripts.probe_vision_memory import measure


def test_component_probe_retains_actual_native_failure_and_unicode():
    code = "import sys; sys.stdout.buffer.write('مرحبا'.encode('utf-8')); sys.stderr.buffer.write(('x'*20000+' خطأ').encode('utf-8')); sys.exit(19)"
    result = measure([sys.executable, "-c", code], sys.executable)
    assert result["exit_code"] == 19 and result["text"] == "مرحبا"
    assert result["stderr_tail"].endswith(" خطأ") and len(result["stderr_tail"]) <= 16000


def test_component_probe_ends_its_owned_worker_at_the_deadline():
    result = measure([sys.executable, "-c", "import time; time.sleep(30)"], sys.executable, timeout_seconds=.05)
    assert result["exit_code"] is None and result["terminated_by_probe"]
    assert "deadline" in result["error"] and result["elapsed_seconds"] < 10


def test_component_probe_retains_failed_launch(tmp_path):
    result = measure([str(tmp_path / "missing-worker")], sys.executable)
    assert result["exit_code"] is None and "Could not start" in result["error"]
    assert not result["text"]
