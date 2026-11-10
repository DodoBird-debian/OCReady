import threading
from pathlib import Path

import pytest
from PIL import Image

from ocready.core.editions import EDITIONS, edition_for
from ocready.core.images import load_image
from ocready.core.preprocess import Recipe, preprocess
from ocready.core.process import run_process
from ocready.core.text import codepoint_offset, parse_tsv, selected_text, utf16_offset
from ocready.core.types import Box, BudgetExceeded, Cancelled, OCRError


def test_editions_use_decimal_bytes():
    assert [v.budget for v in EDITIONS.values()] == [350_000_000, 1_000_000_000, 4_000_000_000]
    with pytest.raises(ValueError):
        edition_for("tiny")


def test_tsv_preserves_logical_arabic_order():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    tsv = header + "5\t1\t1\t1\t1\t1\t200\t10\t70\t30\t96\tمرحبا\n5\t1\t1\t1\t1\t2\t100\t10\t80\t30\t90\tبالعالم\n"
    result = parse_tsv(tsv)
    assert result.text == "مرحبا بالعالم"
    assert result.words[0].box.x == 200
    assert result.text[result.words[1].start:result.words[1].end] == "بالعالم"
    assert result.confidence == 93
    assert selected_text(result.words, {0, 1}) == result.text


def test_empty_and_malformed_tsv():
    assert not parse_tsv("").words
    assert not parse_tsv("level\ttext\n5\tabc\n").words


def test_utf16_offsets_account_for_non_bmp():
    value = "Hi 🐦 مرحبا"
    for offset in range(len(value) + 1):
        assert codepoint_offset(value, utf16_offset(value, offset)) == offset


def test_image_alpha_and_exif_safety(tmp_path):
    path = tmp_path / "صورة.png"
    Image.new("RGBA", (16, 12), (0, 0, 0, 0)).save(path)
    image = load_image(path, EDITIONS["pocket"])
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (255, 255, 255)


def test_large_image_rejected_before_decode(tmp_path):
    path = tmp_path / "large.png"
    Image.new("1", (4000, 2000)).save(path)
    with pytest.raises(OCRError, match="million pixels"):
        load_image(path, EDITIONS["pocket"])


def test_corrupt_image_is_actionable(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")
    with pytest.raises(OCRError, match="cannot be read"):
        load_image(path, EDITIONS["pocket"])


def test_preprocessing_is_reversible_and_bounded():
    source = Image.new("RGB", (100, 50), (0, 10, 20))
    edition = EDITIONS["pocket"]
    image = preprocess(source, Recipe(invert=True, rotation=90), edition)
    assert image.size == (50, 100)
    assert image.getpixel((0, 0)) == (255, 245, 235)
    assert source.getpixel((0, 0)) == (0, 10, 20)
    assert preprocess(source, Recipe(), edition).tobytes() == source.tobytes()
    scaled = preprocess(source, Recipe(scale=100), edition)
    assert scaled.width * scaled.height <= edition.max_pixels


def test_crop_rejects_empty_area():
    with pytest.raises(ValueError, match="nonempty"):
        preprocess(Image.new("RGB", (10, 10)), Recipe(crop=Box(11, 0, 5, 5)), EDITIONS["pocket"])


def test_subprocess_cancellation_and_budget():
    import sys
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        run_process([sys.executable, "-c", "print('x')"], budget=4_000_000_000, cancel=event)
    with pytest.raises(BudgetExceeded):
        run_process([sys.executable, "-c", "print('x')"], budget=1)


def test_subprocess_timeout_and_live_cancellation():
    import sys
    with pytest.raises(OCRError, match="too long"):
        run_process([sys.executable, "-c", "import time; time.sleep(10)"], budget=4_000_000_000, timeout=.1)
    event = threading.Event()
    timer = threading.Timer(.1, event.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            run_process([sys.executable, "-c", "import time; time.sleep(10)"], budget=4_000_000_000, cancel=event)
    finally:
        timer.cancel()


def test_process_arguments_are_not_shell_code(tmp_path):
    import sys
    payload = f"$(touch {tmp_path / 'unsafe'})"
    result = run_process([sys.executable, "-c", "import sys; print(sys.argv[1])", payload], budget=4_000_000_000)
    assert result.stdout.strip() == payload
    assert not (tmp_path / "unsafe").exists()


def test_real_offline_english_ocr(tmp_path):
    from PIL import ImageDraw, ImageFont

    from ocready.core.pipeline import Request, recognize_image
    from ocready.engines.tesseract import readiness
    if not readiness()[0]:
        pytest.skip("Run scripts/prepare_runtime.py for real-engine tests")
    fonts = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    font = ImageFont.truetype(str(next(p for p in fonts if p.exists())), 44)
    image = Image.new("RGB", (820, 140), "white")
    ImageDraw.Draw(image).text((30, 35), "OCReady reads English 123", fill="black", font=font)
    result, _ = recognize_image(image, Request(EDITIONS["pocket"], language="eng", layout="block"))
    assert "reads English 123" in result.text
    assert len(result.words) >= 4
    assert result.peak_rss < EDITIONS["pocket"].budget


def test_real_bilingual_fixture_preserves_arabic():
    from ocready.core.pipeline import Request, recognize_image
    from ocready.engines.tesseract import readiness
    if not readiness()[0]:
        pytest.skip("Run scripts/prepare_runtime.py for real-engine tests")
    fixture = Path(__file__).resolve().parents[1] / "assets" / "sample-bilingual.png"
    source = load_image(fixture, EDITIONS["pocket"])
    result, candidates = recognize_image(source, Request(EDITIONS["pocket"], layout="sparse", compare=True))
    assert "مرحبا بالعالم" in result.text
    assert "اللغة العربية واللغة الإنجليزية" in result.text
    assert "screenshots" in result.text
    assert len(candidates) == 2
    assert all(0 <= word.box.x < source.width for word in result.words)
