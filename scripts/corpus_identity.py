"""Stable accuracy-corpus identity, retaining exact legacy file checksums."""
import hashlib
import json
from pathlib import Path


def corpus_content_sha256(corpus: dict) -> str:
    data = json.dumps(corpus, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_corpus_identity(path: Path) -> tuple[dict, str, set[str]]:
    raw = path.read_bytes()
    corpus = json.loads(raw)
    # Git checkout may translate physical JSON line endings on Windows. Escaped
    # newlines within expected text and all image/recipe records stay intact.
    lf = raw.replace(b"\r\n", b"\n")
    legacy = {hashlib.sha256(data).hexdigest() for data in (lf, lf.replace(b"\n", b"\r\n"))}
    return corpus, corpus_content_sha256(corpus), legacy
