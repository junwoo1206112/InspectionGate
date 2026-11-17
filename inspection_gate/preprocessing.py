"""Single shared preprocessing contract for training and ONNX serving.

Training, export smoke tests and the ONNX provider must use the exact same
resize/scale/normalize order or parity and evaluation are meaningless.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

INPUT_SIZE = 32
CLASS_ORDER = ("good", "defect")
NORMALIZATION = {"mean": 0.5, "std": 0.5, "scale": 255.0}
PREPROCESSING_ID = "rgb-resize32-normalize05-v1"


def preprocess_image_bytes(content: bytes) -> np.ndarray:
    """Return one normalized CHW float32 tensor as a ``(1, 3, H, W)`` array."""
    with Image.open(io.BytesIO(content)) as image:
        image = image.convert("RGB").resize((INPUT_SIZE, INPUT_SIZE), Image.Resampling.BILINEAR)
        array = np.asarray(image, dtype=np.float32) / NORMALIZATION["scale"]
    normalized = (array - NORMALIZATION["mean"]) / NORMALIZATION["std"]
    return np.transpose(normalized, (2, 0, 1))[None, ...].astype(np.float32)


def softmax(logits: np.ndarray) -> np.ndarray:
    """Numerically stable row-wise softmax; not a calibrated probability claim."""
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponentiated = np.exp(shifted)
    return exponentiated / exponentiated.sum(axis=1, keepdims=True)
