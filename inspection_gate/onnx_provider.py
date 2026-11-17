"""ONNX Runtime provider that activates only when an exported artifact exists."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from inspection_gate.inference import ArtifactManifest, ModelUnavailableError
from inspection_gate.preprocessing import preprocess_image_bytes, softmax


class OnnxProvider:
    """Return a model proposal; the reviewer always makes the final decision."""

    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("artifact manifest must be a JSON object")
        self.manifest = ArtifactManifest(**payload)
        self._session = None

    def _onnx_path(self) -> Path | None:
        if not self.manifest.onnx_path:
            return None
        path = Path(self.manifest.onnx_path)
        return path if path.is_absolute() else self.manifest_path.parent / path

    def _session_for(self):
        import onnxruntime

        if self._session is None:
            path = self._onnx_path()
            if path is None or not path.is_file():
                raise ModelUnavailableError("exported ONNX file is unavailable")
            self._session = onnxruntime.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
        return self._session

    def readiness(self) -> dict:
        path = self._onnx_path()
        if self.manifest.status != "exported":
            return {"model_ready": False, "artifact_status": self.manifest.status, "reason": self.manifest.reason}
        if path is None or not path.is_file():
            return {"model_ready": False, "artifact_status": self.manifest.status, "reason": "exported ONNX file is unavailable"}
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return {"model_ready": False, "artifact_status": self.manifest.status, "reason": "onnxruntime is not installed"}
        return {"model_ready": True, "artifact_status": self.manifest.status, "model_id": self.manifest.model_id}

    def predict(self, content: bytes) -> dict:
        if not content:
            raise ValueError("empty image content")
        session = self._session_for()
        try:
            inputs = preprocess_image_bytes(content)
        except (OSError, ValueError, SyntaxError) as error:
            raise ValueError("image could not be decoded for inference") from error
        input_name = self.manifest.input_name or session.get_inputs()[0].name
        output_name = self.manifest.output_name or session.get_outputs()[0].name
        logits = session.run([output_name], {input_name: inputs})[0]
        probabilities = softmax(logits)[0]
        class_order = self.manifest.class_order or ["good", "defect"]
        index = int(probabilities.argmax())
        return {
            "proposal_only": True,
            "proposal_label": class_order[index],
            "max_probability": float(probabilities[index]),
            "probabilities": {label: float(probabilities[i]) for i, label in enumerate(class_order)},
            "class_order": list(class_order),
            "model_version": self.manifest.model_id,
            "model_id": self.manifest.model_id,
            "preprocessing_id": self.manifest.preprocessing_id,
            "input_sha256": hashlib.sha256(content).hexdigest(),
            "scope": "model proposal only; a human reviewer makes the final decision",
        }
