"""FastAPI adapter and local reviewer UI for the InspectionGate demo.

The UI uses declared scenarios. It does not run a production model or control
factory equipment.
"""

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from inspection_gate.domain import Decision, DemoScenario, InspectionService, ReviewError, Status
from inspection_gate.inference import ArtifactManifest, ModelUnavailableError, UnavailableProvider
from inspection_gate.onnx_provider import OnnxProvider

ARTIFACT_MANIFEST_ENV = "INSPECTION_GATE_ARTIFACT_MANIFEST"
AUDIT_PATH_ENV = "INSPECTION_GATE_AUDIT_PATH"
STORE_PATH_ENV = "INSPECTION_GATE_STORE_PATH"
REDIS_URL_ENV = "INSPECTION_GATE_REDIS_URL"
IDEMPOTENCY_TTL_ENV = "INSPECTION_GATE_IDEMPOTENCY_TTL_SECONDS"


def build_inference_provider(manifest_path: str | None = None):
    """Use a real ONNX artifact only when explicitly configured."""
    value = manifest_path if manifest_path is not None else os.environ.get(ARTIFACT_MANIFEST_ENV)
    if not value:
        return UnavailableProvider()
    try:
        return OnnxProvider(Path(value))
    except (OSError, TypeError, ValueError, KeyError) as error:
        return UnavailableProvider(
            ArtifactManifest(
                status="invalid_artifact_manifest",
                reason=f"configured artifact manifest is invalid: {error}",
            )
        )


app = FastAPI(title="InspectionGate", version="0.1.0")
audit_path = Path(os.environ.get(AUDIT_PATH_ENV, "artifacts/audit.jsonl"))
store_path = os.environ.get(STORE_PATH_ENV)
try:
    idempotency_ttl_seconds = int(os.environ.get(IDEMPOTENCY_TTL_ENV, "86400"))
except ValueError:
    idempotency_ttl_seconds = 86_400
redis_url = os.environ.get(REDIS_URL_ENV)
if redis_url:
    from inspection_gate.redis_store import RedisStore

    service = InspectionService(
        audit_path,
        store=RedisStore(redis_url, ttl_seconds=idempotency_ttl_seconds),
    )
else:
    service = InspectionService(
        audit_path,
        store_path=Path(store_path) if store_path else None,
        idempotency_ttl_seconds=idempotency_ttl_seconds,
    )
inference_provider = build_inference_provider()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ReviewRequest(BaseModel):
    decision: Decision
    reason: str
    corrected_label: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "scope": "local decision-support demo",
        "store": service.store_name,
        **inference_provider.readiness(),
    }


@app.get("/ready")
def ready() -> dict:
    readiness = inference_provider.readiness()
    if not readiness["model_ready"]:
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_READY", **readiness})
    return readiness


@app.get("/", include_in_schema=False)
def reviewer_ui() -> FileResponse:
    return FileResponse(static_dir / "index.html", media_type="text/html; charset=utf-8")


@app.post("/predictions")
async def create_prediction(
    file: UploadFile,
    proposal_label: str | None = None,
    max_probability: float | None = None,
    demo_scenario: DemoScenario | None = None,
) -> dict:
    content = await file.read()
    scenario_values = {
        DemoScenario.NORMAL: ("scratch", 0.93, True),
        DemoScenario.LOW_SCORE: ("scratch", 0.52, True),
        DemoScenario.INPUT_QUALITY: (None, None, False),
    }
    if demo_scenario is not None:
        proposal_label, max_probability, input_quality_ok = scenario_values[demo_scenario]
    else:
        input_quality_ok = True
    prediction = service.create_prediction(
        input_name=file.filename or "unnamed",
        content=content,
        proposal_label=proposal_label,
        max_probability=max_probability,
        model_version="scenario-demo-v1" if demo_scenario else "demo-model-unset",
        input_quality_ok=input_quality_ok,
    )
    return asdict(prediction)


def _prediction_summary(prediction) -> dict:
    payload = asdict(prediction)
    payload.pop("audit_history", None)
    return payload


@app.get("/predictions")
def list_predictions(
    status: Status | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    try:
        return [_prediction_summary(prediction) for prediction in service.list_predictions(status, limit)]
    except ReviewError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str) -> dict:
    try:
        return asdict(service.get_prediction(prediction_id))
    except ReviewError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/predict")
async def predict(file: UploadFile) -> dict:
    """Real-inference endpoint whose proposal enters the review and audit flow."""
    content = await file.read()
    input_name = file.filename or "unnamed"
    extension_ok = Path(input_name).suffix.lower() in InspectionService.allowed_extensions
    if not content or not extension_ok:
        prediction = service.create_prediction(
            input_name=input_name,
            content=content,
            proposal_label=None,
            max_probability=None,
            model_version="input-quality-gate",
            input_quality_ok=False,
        )
        return {
            **asdict(prediction),
            "proposal_only": True,
            "inference": "not_run_input_quality",
            "scope": "input quality HOLD; upload a replacement image",
        }
    try:
        proposal = inference_provider.predict(content)
    except ModelUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_NOT_READY", "message": str(error), "scope": "no verified model artifact"},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_IMAGE", "message": str(error)},
        ) from error
    prediction = service.create_prediction(
        input_name=input_name,
        content=content,
        proposal_label=proposal.get("proposal_label"),
        max_probability=proposal.get("max_probability"),
        model_version=proposal.get("model_version") or "unknown-model",
        input_quality_ok=True,
    )
    return {
        **asdict(prediction),
        "proposal_only": True,
        "probabilities": proposal.get("probabilities"),
        "class_order": proposal.get("class_order"),
        "preprocessing_id": proposal.get("preprocessing_id"),
        "scope": proposal.get("scope", "model proposal only; a human reviewer makes the final decision"),
    }


@app.post("/predictions/{prediction_id}/review")
def review_prediction(
    prediction_id: str,
    request: ReviewRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    if idempotency_key is not None:
        if not idempotency_key.strip():
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_IDEMPOTENCY_KEY", "message": "Idempotency-Key must be nonempty"},
            )
        if len(idempotency_key) > 255:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_IDEMPOTENCY_KEY", "message": "Idempotency-Key must be at most 255 characters"},
            )
    try:
        return asdict(service.decide(
            prediction_id, request.decision, request.reason, request.corrected_label,
            idempotency_key=idempotency_key,
        ))
    except ReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/predictions/{prediction_id}/audit")
def audit(prediction_id: str) -> list[dict]:
    try:
        return service.audit(prediction_id)
    except ReviewError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
