"""FastAPI application entrypoint and HTTP endpoints for FinOps Sentinel."""

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings
from app.detector import AnomalyDetector
from app.schemas import AnomalyReport, CostRecord, ProjectGuardResponse

app = FastAPI(
    title="FinOps Sentinel",
    description=(
        "Real-time cloud cost anomaly detection microservice "
        "with multi-tenant isolation."
    ),
    version="0.2.0",
)

detector = AnomalyDetector()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str | None:
    """Validate X-API-Key header against configured application secret."""
    if settings.api_key is not None and api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key authentication header.",
        )
    return api_key


@app.get("/healthz", tags=["Health"])
def health_check() -> dict[str, str]:
    """Return liveness and readiness status for Kubernetes orchestration."""
    return {"status": "ok"}


@app.post(
    "/api/v1/telemetry",
    response_model=AnomalyReport,
    dependencies=[Depends(verify_api_key)],
    tags=["Telemetry"],
)
def ingest_telemetry(record: CostRecord) -> AnomalyReport:
    """Ingest a cloud cost telemetry record and evaluate it for cost anomalies."""
    return detector.evaluate(record)


@app.get(
    "/api/v1/alerts",
    response_model=list[AnomalyReport],
    dependencies=[Depends(verify_api_key)],
    tags=["Alerts"],
)
def list_alerts(project: str | None = None) -> list[AnomalyReport]:
    """Return the historical list of detected cost anomalies."""
    return detector.get_alerts(project=project)


@app.get(
    "/api/v1/guard/{project}",
    response_model=ProjectGuardResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Guard"],
)
def check_project_guard(project: str) -> ProjectGuardResponse:
    """Return circuit breaker execution permission for a given project."""
    return detector.get_guard_status(project=project)
