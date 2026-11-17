"""Inference-readiness contracts for a future ONNX provider.

No model is bundled with this project.  These objects make absence explicit so
that a UI/demo path cannot be mistaken for a real model prediction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class ModelUnavailableError(RuntimeError):
    """Raised when a prediction request has no verified model artifact."""


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    status: str = "not_exported"
    model_id: str | None = None
    model_sha256: str | None = None
    checkpoint_path: str | None = None
    onnx_path: str | None = None
    onnx_sha256: str | None = None
    artifact_origin: str | None = None
    lineage_id: str | None = None
    preprocessing_id: str | None = None
    class_order: list[str] | None = None
    input_name: str | None = None
    input_shape: list[int] | None = None
    input_dtype: str | None = None
    output_name: str | None = None
    opset: int | None = None
    exporter_version: str | None = None
    runtime_version: str | None = None
    reason: str = "No verified PyTorch/ONNX artifact has been supplied."

    def to_dict(self) -> dict:
        return asdict(self)


class InferenceProvider(Protocol):
    def readiness(self) -> dict: ...

    def predict(self, content: bytes) -> dict: ...


class UnavailableProvider:
    """Default provider: it rejects instead of manufacturing an inference result."""

    def __init__(self, manifest: ArtifactManifest | None = None) -> None:
        self.manifest = manifest or ArtifactManifest()

    def readiness(self) -> dict:
        return {"model_ready": False, "artifact_status": self.manifest.status, "reason": self.manifest.reason}

    def predict(self, content: bytes) -> dict:
        raise ModelUnavailableError(self.manifest.reason)


def parity_preflight(manifest: ArtifactManifest, *, onnxruntime_available: bool = False) -> dict:
    """Report whether a true PyTorch/ONNX parity run may start.

    It intentionally returns a skipped result for absent artifacts rather than
    calling that condition a successful parity test.
    """
    missing = []
    if manifest.status != "exported":
        missing.append("artifact status is not exported")
    if not manifest.onnx_path or not Path(manifest.onnx_path).is_file():
        missing.append("ONNX file is unavailable")
    if not manifest.class_order or not manifest.preprocessing_id:
        missing.append("preprocessing/class order contract is incomplete")
    if not onnxruntime_available:
        missing.append("onnxruntime is not available")
    if missing:
        return {"status": "skipped", "reason": "; ".join(missing), "metrics": None}
    return {"status": "ready", "reason": "artifact and runtime prerequisites are present", "metrics": None}
