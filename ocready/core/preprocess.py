from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageOps

from ocready.core.editions import Edition
from ocready.core.images import fit_image
from ocready.core.types import Box


@dataclass(frozen=True)
class Recipe:
    invert: bool = False
    grayscale: bool = False
    autocontrast: bool = False
    contrast: float = 1.0
    threshold: int | None = None
    rotation: int = 0
    mirror: bool = False
    flip: bool = False
    crop: Box | None = None
    scale: float = 1.0

    @property
    def label(self) -> str:
        labels = []
        if self.crop:
            labels.append("Cropped")
        if self.rotation % 360:
            labels.append(f"Rotate {self.rotation % 360}°")
        if self.mirror:
            labels.append("Mirror")
        if self.flip:
            labels.append("Flip")
        if self.invert:
            labels.append("Invert")
        if self.grayscale:
            labels.append("Grayscale")
        if self.autocontrast:
            labels.append("Auto contrast")
        if self.contrast != 1:
            labels.append(f"Contrast {self.contrast:g}×")
        if self.threshold is not None:
            labels.append(f"Threshold {self.threshold}")
        if self.scale != 1:
            labels.append(f"Scale {self.scale:g}×")
        return " · ".join(labels) or "Original"


def preprocess(source: Image.Image, recipe: Recipe, edition: Edition) -> Image.Image:
    image = source.copy()
    if recipe.crop:
        c = recipe.crop
        left, top = min(c.x, image.width), min(c.y, image.height)
        right, bottom = min(c.x + c.width, image.width), min(c.y + c.height, image.height)
        if right <= left or bottom <= top:
            raise ValueError("Select a nonempty crop inside the image.")
        image = image.crop((left, top, right, bottom))
    rotations = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}
    if recipe.rotation % 360 in rotations:
        image = image.transpose(rotations[recipe.rotation % 360])
    if recipe.mirror:
        image = ImageOps.mirror(image)
    if recipe.flip:
        image = ImageOps.flip(image)
    if recipe.invert:
        image = ImageOps.invert(image)
    if recipe.grayscale:
        image = ImageOps.grayscale(image)
    if recipe.autocontrast:
        image = ImageOps.autocontrast(image)
    if recipe.contrast != 1:
        image = ImageEnhance.Contrast(image).enhance(recipe.contrast)
    if recipe.threshold is not None:
        image = ImageOps.grayscale(image).point(lambda value: 255 if value >= recipe.threshold else 0)
    if recipe.scale != 1:
        # Fit the desired dimensions before allocation, rather than upscaling then shrinking.
        import math
        factor = min(recipe.scale, edition.max_edge / max(image.size),
                     math.sqrt(edition.max_pixels / (image.width * image.height)))
        image = image.resize((max(1, int(image.width * factor)), max(1, int(image.height * factor))),
                             Image.Resampling.LANCZOS)
    return fit_image(image, edition).convert("RGB")
