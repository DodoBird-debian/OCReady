import json
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from scripts.benchmark import check_requested_engine, observe, redact_details
from scripts.smoke_binary import run_checked


def test_failed_packaged_command_retains_bounded_unicode_diagnostics(tmp_path):
    output = tmp_path / "error.log"
    program = "import sys; sys.stdout.write('x'*90000); sys.stdout.flush(); sys.stderr.buffer.write('OCR failed: العربية\\n'.encode('utf-8')); sys.stderr.flush(); sys.exit(2)"
    with pytest.raises(subprocess.CalledProcessError):
        run_checked([sys.executable, "-c", program], diagnostic=output)
    log = output.read_text(encoding="utf-8")
    assert log.endswith("OCR failed: العربية\n")
    assert len(log) <= 65536


def test_resource_workload_cannot_pass_after_silently_selecting_another_engine():
    for method, pack, actual, expected_status in [("neural", "bilingual", "tesseract-best", 2),
                                                 ("vision", "large", "vision:small", 2),
                                                 ("vision", "large", "vision:large", 0),
                                                 ("vision", None, "vision:large", 0)]:
        result = {"exit_code": 0, "details": {"engine": actual}}
        check_requested_engine(result, method, pack)
        assert result["exit_code"] == expected_status


def test_failed_gui_benchmark_preserves_error_without_document_contents():
    safe = redact_details({"text": "private text", "words": 0, "error": "Model exceeds budget", "rss": 500})
    assert safe == {"words": 0, "error": "Model exceeds budget", "rss": 500}
    assert redact_details({"text": "private", "result": {"text": "private", "words": [{"text": "private"}], "engine": "vision"}}) == {"words": 1, "engine": "vision"}


def test_benchmark_refuses_success_without_a_valid_result_file(tmp_path):
    output = tmp_path / "missing.json"
    result = observe([sys.executable, "-c", "pass"], output, 4_000_000_000)
    assert result["exit_code"] != 0
    assert result["details"]["error"]
    output.write_text('{"error":"GUI timed out"}', encoding="utf-8")
    result = observe([sys.executable, "-c", "pass"], output, 4_000_000_000)
    assert result["exit_code"] != 0



def test_benchmark_reads_arabic_under_a_windows_codepage(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    output.write_text(json.dumps({"text": "مرحبا بالعالم"}, ensure_ascii=False), encoding="utf-8")
    original_read = Path.read_text
    def windows_default(path, *args, **kwargs):
        if path == output:
            kwargs.setdefault("encoding", "cp1252")
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", windows_default)
    result = observe([sys.executable, "-c", "pass"], output, 4_000_000_000)
    assert result["details"]["text"] == "مرحبا بالعالم"


def test_deadline_failure_preserves_a_result_instead_of_discarding_measurements(tmp_path):
    output = tmp_path / "result.json"
    result = observe([sys.executable, "-c", "import time; time.sleep(10)"], output, 4_000_000_000, timeout_seconds=.05)
    assert result["exit_code"] and result["timed_out"]
    assert result["timeout_seconds"] == .05
    assert "exceeded" in result["details"]["error"]
    assert result["peak_rss_bytes"] > 0 and result["below_budget"]


def test_smoke_timeout_cleans_the_onefile_style_descendant_tree(tmp_path):
    pid_file = tmp_path / "child.pid"
    program = ("import subprocess, sys, time\nfrom pathlib import Path\n"
               "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
               f"Path({str(pid_file)!r}).write_text(str(child.pid))\n"
               "time.sleep(30)\n")
    with pytest.raises(subprocess.TimeoutExpired):
        run_checked([sys.executable, "-c", program], timeout=2)
    try:
        assert psutil.Process(int(pid_file.read_text())).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass
