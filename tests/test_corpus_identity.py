import copy
import json

from scripts.corpus_identity import corpus_content_sha256, load_corpus_identity


def test_corpus_identity_ignores_only_json_formatting_and_keeps_raw_checksums(tmp_path):
    corpus = {"cases": [{"expected": "مَرْحَبًا ٢٥٠٠\nText", "image_sha256": "a" * 64, "recipe": {"invert": True}}]}
    path = tmp_path / "manifest.json"
    text = json.dumps(corpus, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))
    lf = load_corpus_identity(path)
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert load_corpus_identity(path) == lf
    assert len(lf[2]) == 2
    assert corpus_content_sha256(json.loads(json.dumps(corpus))) == lf[1]
    for field, value in (("expected", "مرحبا ٢٥٠٠\nText"), ("expected", "مَرْحَبًا ٢٠٠٠\nText"),
                         ("image_sha256", "b" * 64), ("recipe", {"invert": False})):
        changed = copy.deepcopy(corpus)
        changed["cases"][0][field] = value
        assert corpus_content_sha256(changed) != lf[1]
