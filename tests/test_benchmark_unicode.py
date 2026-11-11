import json
import sys
from pathlib import Path

from scripts.benchmark import check_requested_engine, observe, redact_details


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
