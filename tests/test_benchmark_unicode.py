import json
from pathlib import Path


def test_benchmark_reads_arabic_under_a_windows_codepage(tmp_path, monkeypatch):
    import sys

    from scripts.benchmark import observe
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
