"""Small deterministic PyTorch model for the synthetic reference pipeline.

This is a reference implementation, not a production anomaly detector.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import torch
from torch import nn

from inspection_gate.preprocessing import CLASS_ORDER, INPUT_SIZE

ARCHITECTURE = "TinyDefectCNN"


class TinyDefectCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(8, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        reduced = INPUT_SIZE // 4
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * reduced * reduced, 16),
            nn.ReLU(),
            nn.Linear(16, len(CLASS_ORDER)),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(inputs))


def set_determinism(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def save_checkpoint(path: str | Path, model: TinyDefectCNN, metadata: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "metadata": metadata}, target)


def load_checkpoint(path: str | Path) -> tuple[TinyDefectCNN, dict]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    model = TinyDefectCNN()
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, dict(payload.get("metadata", {}))
