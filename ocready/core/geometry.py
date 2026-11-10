"""Project located OCR boxes back onto the untouched working source image."""
import math
from dataclasses import replace

from ocready.core.preprocess import Recipe
from ocready.core.types import Box, Word


def box_on_source(box: Box, source_size: tuple[int, int], processed_size: tuple[int, int], recipe: Recipe) -> Box:
    source_width, source_height = source_size
    processed_width, processed_height = processed_size
    if min(source_width, source_height, processed_width, processed_height) <= 0:
        raise ValueError("Images need positive dimensions for source highlighting.")
    crop = recipe.crop
    left = min(crop.x, source_width) if crop else 0
    top = min(crop.y, source_height) if crop else 0
    right = min(crop.x + crop.width, source_width) if crop else source_width
    bottom = min(crop.y + crop.height, source_height) if crop else source_height
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ValueError("The crop is outside the source image.")
    rotation = recipe.rotation % 360
    if rotation not in {0, 90, 180, 270}:
        raise ValueError("Source highlighting requires a quarter-turn rotation.")
    rotated_width, rotated_height = (height, width) if rotation in {90, 270} else (width, height)
    points = []
    for x, y in ((box.x, box.y), (box.x + box.width, box.y),
                 (box.x, box.y + box.height), (box.x + box.width, box.y + box.height)):
        x, y = x * rotated_width / processed_width, y * rotated_height / processed_height
        if recipe.flip:
            y = rotated_height - y
        if recipe.mirror:
            x = rotated_width - x
        if rotation == 90:
            x, y = y, height - x
        elif rotation == 180:
            x, y = width - x, height - y
        elif rotation == 270:
            x, y = width - y, x
        points.append((x + left, y + top))
    x1 = max(0, min(source_width, math.floor(min(p[0] for p in points))))
    y1 = max(0, min(source_height, math.floor(min(p[1] for p in points))))
    x2 = max(x1, min(source_width, math.ceil(max(p[0] for p in points))))
    y2 = max(y1, min(source_height, math.ceil(max(p[1] for p in points))))
    return Box(x1, y1, x2 - x1, y2 - y1)


def words_on_source(words: list[Word], source_size: tuple[int, int], processed_size: tuple[int, int], recipe: Recipe) -> list[Word]:
    # Keep order and character ranges identical so selections use the same indices
    # in either picture view; only the pixel coordinates change.
    return [replace(word, box=box_on_source(word.box, source_size, processed_size, recipe)) for word in words]
