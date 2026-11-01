"""FastAPI application entrypoint and HTTP endpoints for FinOps Sentinel."""

from typing import List

from fastapi import FastAPI

from app.detector import AnomalyDetector
from app.schemas import AnomalyReport, CostRecord

app = FastAPI(
    title="FinOps Sentinel",
    description="Real-time cloud cost anomaly detection microservice.",
    version="0.1.0",
)

detector = AnomalyDetector()


@app.post("/api/v1/telemetry", response_model=AnomalyReport)
def ingest_telemetry(record: CostRecord) -> AnomalyReport:
    """Ingest a cloud cost telemetry record and evaluate it for cost anomalies."""
    return detector.evaluate(record)


@app.get("/api/v1/alerts", response_model=List[AnomalyReport])
def list_alerts() -> List[AnomalyReport]:
    """Return the historical list of all detected cost anomalies."""
    return detector.get_alerts()
