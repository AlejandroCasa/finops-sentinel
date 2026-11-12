"""FastAPI application entrypoint and HTTP endpoints for FinOps Sentinel."""

from fastapi import FastAPI, Response

from app.detector import AnomalyDetector
from app.metrics import metrics_registry
from app.schemas import AnomalyReport, CostRecord

app = FastAPI(
    title="FinOps Sentinel",
    description="Real-time cloud cost anomaly detection microservice.",
    version="0.1.0",
)

detector = AnomalyDetector()


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


@app.post("/api/v1/telemetry", response_model=AnomalyReport)
def ingest_telemetry(record: CostRecord) -> AnomalyReport:
    """Ingest a cloud cost telemetry record and evaluate it for cost anomalies."""
    report = detector.evaluate(record)
    metrics_registry.record_telemetry(
        service=record.service_name,
        currency=record.currency,
        cost=record.cost_amount,
    )
    if report.is_anomaly:
        metrics_registry.record_anomaly(service=record.service_name)
    return report


@app.get("/api/v1/alerts", response_model=list[AnomalyReport])
def list_alerts() -> list[AnomalyReport]:
    """Return the historical list of all detected cost anomalies."""
    return detector.get_alerts()
