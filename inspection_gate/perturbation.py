"""Deterministic image perturbations for robustness measurement only.

Perturbation results on synthetic images are a toolchain and evaluation-method
check. They are not factory, benchmark or generalization evidence.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class PerturbationSpec:
    name: str
    description: str


PERTURBATIONS: tuple[PerturbationSpec, ...] = (
    PerturbationSpec("identity", "unchanged decoded image"),
    PerturbationSpec("gaussian_noise", "deterministic additive pixel noise"),
    PerturbationSpec("blur", "gaussian blur radius 1.2"),
    PerturbationSpec("brightness_low", "brightness multiplied by 0.7"),
    PerturbationSpec("contrast_low", "contrast multiplied by 0.7"),
    PerturbationSpec("jpeg_q30", "JPEG round trip at quality 30"),
    PerturbationSpec("downscale_16", "downscale to 16 px then back to original size"),
)


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _noise(image: Image.Image, seed: int, sample_id: str) -> Image.Image:
    digest = hashlib.sha256(f"{seed}:{sample_id}:gaussian_noise".encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    array = np.asarray(image.convert("RGB"), dtype=np.int16)
    noise = rng.integers(-18, 19, size=array.shape, dtype=np.int16)
    return Image.fromarray(np.clip(array + noise, 0, 255).astype(np.uint8), mode="RGB")


def _jpeg_round_trip(image: Image.Image, quality: int = 30) -> Image.Image:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as reopened:
        return reopened.convert("RGB").copy()


def _downscale(image: Image.Image, size: int = 16) -> Image.Image:
    original = image.size
    resized = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    return resized.resize(original, Image.Resampling.BILINEAR)


def apply_perturbation(
    image: Image.Image, name: str, *, seed: int = 20261109, sample_id: str = ""
) -> Image.Image:
    if name == "identity":
        return image.convert("RGB").copy()
    if name == "gaussian_noise":
        return _noise(image, seed, sample_id)
    if name == "blur":
        return image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=1.2))
    if name == "brightness_low":
        return ImageEnhance.Brightness(image.convert("RGB")).enhance(0.7)
    if name == "contrast_low":
        return ImageEnhance.Contrast(image.convert("RGB")).enhance(0.7)
    if name == "jpeg_q30":
        return _jpeg_round_trip(image)
    if name == "downscale_16":
        return _downscale(image)
    raise ValueError(f"unknown perturbation: {name}")


def perturb_image_bytes(
    content: bytes, name: str, *, seed: int = 20261109, sample_id: str = ""
) -> bytes:
    """Apply one perturbation and re-encode as PNG for the shared preprocessing path."""
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        changed = apply_perturbation(image, name, seed=seed, sample_id=sample_id)
    return _png_bytes(changed)
