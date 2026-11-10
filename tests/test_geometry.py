import pytest
from PIL import Image, ImageDraw, ImageOps

from ocready.core.editions import EDITIONS
from ocready.core.geometry import box_on_source
from ocready.core.preprocess import Recipe, preprocess
from ocready.core.types import Box


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("flip", [False, True])
@pytest.mark.parametrize("crop", [None, Box(5, 10, 70, 40)])
def test_source_projection_matches_actual_transformed_pixels(rotation, mirror, flip, crop):
    source = Image.new("RGB", (100, 60), "white")
    ImageDraw.Draw(source).rectangle((10, 20, 39, 29), fill="black")
    recipe = Recipe(rotation=rotation, mirror=mirror, flip=flip, crop=crop)
    processed = preprocess(source, recipe, EDITIONS["pocket"])
    rectangle = ImageOps.invert(processed.convert("L")).getbbox()
    left, top, right, bottom = rectangle
    located = Box(left, top, right - left, bottom - top)
    assert box_on_source(located, source.size, processed.size, recipe) == Box(10, 20, 30, 10)


def test_source_projection_includes_crop_rotation_flips_and_resize():
    recipe = Recipe(crop=Box(5, 10, 70, 40), rotation=90, mirror=True, flip=True, scale=2)
    assert box_on_source(Box(20, 70, 20, 60), (100, 60), (80, 140), recipe) == Box(10, 20, 30, 10)


def test_source_projection_clamps_invalid_engine_extents():
    assert box_on_source(Box(90, 40, 100, 100), (100, 60), (100, 60), Recipe()) == Box(90, 40, 10, 20)
    with pytest.raises(ValueError):
        box_on_source(Box(0, 0, 1, 1), (100, 60), (0, 60), Recipe())
