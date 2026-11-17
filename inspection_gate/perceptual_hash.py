"""Perceptual-hash near-duplicate links for conservative leakage grouping.

This is a review aid, not proof of duplication. Low-frequency DCT hashing can
miss true duplicates and can collide on low-texture images, so the Hamming
threshold is a caller-reviewed parameter rather than a universal default.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image

METHOD = "pHash-DCT-lowfreq-median-v1"


@lru_cache(maxsize=8)
def _dct_matrix(size: int) -> np.ndarray:
    frequencies = np.arange(size)[:, None]
    positions = np.arange(size)[None, :]
    return np.cos(np.pi * (2 * positions + 1) * frequencies / (2 * size))


@dataclass(frozen=True)
class PerceptualHashConfig:
    enabled: bool = False
    max_hamming: int = 6
    hash_size: int = 8
    highfreq_factor: int = 4
    min_texture_std: float = 2.0

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        if type(self.max_hamming) is not int or not 0 <= self.max_hamming <= self.hash_size**2:
            raise ValueError("max_hamming must be an integer within 0..hash_size**2")
        if type(self.hash_size) is not int or not 1 <= self.hash_size <= 16:
            raise ValueError("hash_size must be an integer within 1..16")
        if type(self.highfreq_factor) is not int or not 1 <= self.highfreq_factor <= 8:
            raise ValueError("highfreq_factor must be an integer within 1..8")
        if not isinstance(self.min_texture_std, (int, float)) or isinstance(self.min_texture_std, bool):
            raise ValueError("min_texture_std must be a non-negative number")
        if not np.isfinite(self.min_texture_std) or self.min_texture_std < 0:
            raise ValueError("min_texture_std must be a finite non-negative number")


def grayscale_std(image: Image.Image, *, size: int = 32) -> float:
    """Standard deviation of a low-pass grayscale image, used as a texture guard."""
    gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return float(np.asarray(gray, dtype=np.float64).std())


def phash(image: Image.Image, *, hash_size: int = 8, highfreq_factor: int = 4) -> int:
    size = hash_size * highfreq_factor
    gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.float64)
    matrix = _dct_matrix(size)
    coefficients = matrix @ pixels @ matrix.T
    low_frequency = coefficients[:hash_size, :hash_size].flatten()
    median = np.median(low_frequency[1:])
    bits = 0
    for value in low_frequency:
        bits = (bits << 1) | (1 if value > median else 0)
    return bits


def phash_bytes(content: bytes, *, hash_size: int = 8, highfreq_factor: int = 4) -> int:
    with Image.open(io.BytesIO(content)) as image:
        image.load()
        return phash(image, hash_size=hash_size, highfreq_factor=highfreq_factor)


def phash_hex(value: int, *, hash_size: int = 8) -> str:
    width = (hash_size * hash_size + 3) // 4
    return f"{value:0{width}x}"


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def find_near_duplicate_pairs(hashes: dict[str, int], max_hamming: int) -> list[dict]:
    """Return all pairs at or below the threshold, deterministically ordered."""
    if max_hamming < 0:
        raise ValueError("max_hamming must be non-negative")
    identifiers = sorted(hashes)
    pairs: list[dict] = []
    for index, left in enumerate(identifiers):
        for right in identifiers[index + 1:]:
            distance = hamming(hashes[left], hashes[right])
            if distance <= max_hamming:
                pairs.append({"left": left, "right": right, "hamming_distance": distance})
    return pairs
