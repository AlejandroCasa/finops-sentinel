"""FastAPI application entrypoint and HTTP endpoints for FinOps Sentinel."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings
from app.detector import AnomalyDetector
from app.metrics import metrics_registry
from app.pricing import calculate_llm_cost
from app.schemas import (
    AnomalyReport,
    BatchTelemetryRequest,
    BatchTelemetryResponse,
    CostRecord,
    FOCUSAnomalyReport,
    FOCUSTelemetryRequest,
    LLMAnomalyReport,
    LLMTelemetryRequest,
    ProjectGuardResponse,
)

detector = AnomalyDetector()


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and graceful SQLite draining on shutdown."""
    detector._init_db()
    yield
    detector.close()


app = FastAPI(
    title="FinOps Sentinel",
    description=(
        "Real-time cloud cost anomaly detection microservice "
        "with multi-tenant isolation, batch ingestion, and LLM cost estimation."
    ),
    version="0.4.0",
    lifespan=lifespan,
)

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


@app.get(
    "/metrics",
    tags=["Observability"],
    response_class=Response,
    responses={
        200: {
            "content": {"text/plain; version=0.0.4; charset=utf-8": {}},
            "description": "Prometheus text exposition format.",
        }
    },
)
def get_metrics() -> Response:
    """Export application metrics in standard Prometheus exposition format."""
    payload = metrics_registry.generate_prometheus_exposition()
    return Response(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post(
    "/api/v1/telemetry",
    response_model=AnomalyReport,
    dependencies=[Depends(verify_api_key)],
    tags=["Telemetry"],
)
def ingest_telemetry(record: CostRecord) -> AnomalyReport:
    """Ingest a single cloud cost telemetry record and evaluate for anomalies."""
    report = detector.evaluate(record)
    metrics_registry.record_telemetry(
        service=record.service_name,
        currency=record.currency,
        cost=record.cost_amount,
    )
    if report.is_anomaly:
        metrics_registry.record_anomaly(service=record.service_name)
    return report


@app.post(
    "/api/v1/telemetry/batch",
    response_model=BatchTelemetryResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Telemetry"],
)
def ingest_telemetry_batch(batch: BatchTelemetryRequest) -> BatchTelemetryResponse:
    """Ingest multiple cloud cost telemetry records in a single batch operation."""
    reports: list[AnomalyReport] = []
    anomalies_count = 0

    for record in batch.records:
        report = detector.evaluate(record)
        metrics_registry.record_telemetry(
            service=record.service_name,
            currency=record.currency,
            cost=record.cost_amount,
        )
        if report.is_anomaly:
            anomalies_count += 1
            metrics_registry.record_anomaly(service=record.service_name)
        reports.append(report)

    return BatchTelemetryResponse(
        total_processed=len(batch.records),
        anomalies_detected=anomalies_count,
        reports=reports,
    )


@app.post(
    "/api/v1/telemetry/llm",
    response_model=LLMAnomalyReport,
    dependencies=[Depends(verify_api_key)],
    tags=["Telemetry"],
)
def ingest_llm_telemetry(payload: LLMTelemetryRequest) -> LLMAnomalyReport:
    """Calculate LLM token cost in USD, ingest telemetry, and detect anomalies."""
    cost_usd = calculate_llm_cost(
        model=payload.model,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
    )
    record = CostRecord(
        service_name=payload.service_name,
        cost_amount=cost_usd,
        currency="USD",
        project=payload.project,
        environment=payload.environment,
        owner_team=payload.owner_team,
        commit_sha=payload.commit_sha,
    )
    report = detector.evaluate(record)
    metrics_registry.record_telemetry(
        service=record.service_name,
        currency=record.currency,
        cost=record.cost_amount,
    )
    if report.is_anomaly:
        metrics_registry.record_anomaly(service=record.service_name)

    return LLMAnomalyReport(
        is_anomaly=report.is_anomaly,
        deviation_percentage=report.deviation_percentage,
        current_cost=report.current_cost,
        historical_mean=report.historical_mean,
        service_name=report.service_name,
        project=report.project,
        environment=report.environment,
        owner_team=report.owner_team,
        commit_sha=report.commit_sha,
        timestamp=report.timestamp,
        calculated_cost_usd=cost_usd,
    )


@app.post(
    "/api/v1/telemetry/focus",
    response_model=FOCUSAnomalyReport,
    dependencies=[Depends(verify_api_key)],
    tags=["Telemetry"],
)
def ingest_focus_telemetry(payload: FOCUSTelemetryRequest) -> FOCUSAnomalyReport:
    """Ingest cloud cost telemetry conforming to the FOCUS 1.0 specification."""
    evaluated_cost = (
        payload.effective_cost if payload.effective_cost > 0 else payload.billed_cost
    )
    record = CostRecord(
        service_name=payload.service_name,
        cost_amount=evaluated_cost,
        currency=payload.billing_currency,
        project=payload.sub_account_id,
        environment=payload.environment,
        owner_team=payload.owner_team,
        commit_sha=payload.commit_sha,
    )
    report = detector.evaluate(record)
    metrics_registry.record_telemetry(
        service=record.service_name,
        currency=record.currency,
        cost=record.cost_amount,
    )
    if report.is_anomaly:
        metrics_registry.record_anomaly(service=record.service_name)

    return FOCUSAnomalyReport(
        is_anomaly=report.is_anomaly,
        deviation_percentage=report.deviation_percentage,
        current_cost=report.current_cost,
        historical_mean=report.historical_mean,
        service_name=report.service_name,
        project=report.project,
        environment=report.environment,
        owner_team=report.owner_team,
        commit_sha=report.commit_sha,
        timestamp=report.timestamp,
        billed_cost=payload.billed_cost,
        effective_cost=payload.effective_cost,
        region_id=payload.region_id,
    )


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
