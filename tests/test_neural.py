import dataclasses
import json
from pathlib import Path

import pytest

from native.neural_runner import logical_text
from ocready.core.editions import EDITIONS
from ocready.core.neural_packs import NeuralPack, load_neural_pack
from ocready.core.types import OCRError
from ocready.engines.neural import parse_output


@pytest.fixture
def neural_pack(tmp_path):
    assets = []
    for name in ("runner", "detector", "recognizer", "dictionary"):
        path = tmp_path / name
        path.write_text("abc\n")
        assets.append(str(path))
    return NeuralPack("local", "Local neural OCR", *assets)


def test_neural_pack_validation_and_relative_manifest(neural_pack, tmp_path):
    neural_pack.validate()
    assert neural_pack.admission(EDITIONS["everyday"])[0]
    assert not neural_pack.admission(EDITIONS["pocket"])[0]
    data = neural_pack.to_dict()
    for key in ("runner", "detector", "recognizer", "dictionary"):
        data[key] = Path(data[key]).name
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(data))
    assert load_neural_pack(path) == neural_pack
    with pytest.raises(OCRError, match="Invalid neural manifest"):
        NeuralPack.from_dict({**data, "max_pixels": True})
    with pytest.raises(OCRError, match="Invalid neural manifest"):
        NeuralPack.from_dict({**data, "languages": "unsupported"})
    with pytest.raises(OCRError):
        dataclasses.replace(neural_pack, direction="unknown").validate()


@pytest.mark.parametrize("raw,expected", [("ملاعلاب ابحرم", "مرحبا بالعالم"),
                                         ("OCReady 123 بلطلا مقر", "رقم الطلب OCReady 123"),
                                         ("رانيد ٢٥٠٠ يلامجإلا", "الإجمالي ٢٥٠٠ دينار"),
                                         ("Contact: user@example.com", "Contact: user@example.com"),
                                         ("Order 12345 costs 25.00 USD.", "Order 12345 costs 25.00 USD.")])
def test_neural_ctc_text_becomes_copyable_logical_unicode(raw, expected):
    assert logical_text(raw) == expected
    assert logical_text(expected, decode="logical") == expected


def test_neural_line_geometry_and_offsets_are_real_regions(neural_pack):
    data = {"schema": 1, "width": 100, "height": 80, "backend": "CPU", "lines": [
        {"text": "مرحبا بالعالم", "polygon": [[10.2, 20], [90, 18.5], [91, 40], [10, 41]], "score": .9},
        {"text": "English", "polygon": [[-1, 50], [70, 50], [70, 81], [0, 80]], "score": .8}]}
    result = parse_output(json.dumps(data), (100, 80), pack=neural_pack, language="ara+eng")
    assert result.geometry == "line"
    assert len(result.words) == 2
    assert result.words[0].text == "مرحبا بالعالم"
    assert result.words[1].box.height == 30
    assert result.words[1].box.x == 0
    for region in result.words:
        assert result.text[region.start:region.end] == region.text
    assert result.words[0].confidence == 90


@pytest.mark.parametrize("bad", ["{}", "[]", '{"schema":1,"width":10,"height":10,"backend":"CPU","lines":[{"text":"x","polygon":[[0,0],[1,0],[1,1],[0,1]],"score":NaN}]}'])
def test_malformed_neural_response_is_rejected(neural_pack, bad):
    with pytest.raises(OCRError, match="invalid OCR response"):
        parse_output(bad, (10, 10), pack=neural_pack, language="ara")
