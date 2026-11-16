"""Integration and unit tests for FinOps Sentinel Prometheus metrics exporter."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, detector
from app.metrics import MetricsRegistry, metrics_registry

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state() -> None:
    """Reset detector and metrics state before each test execution."""
    detector.history.clear()
    detector.alerts.clear()
    metrics_registry.reset()


def test_metrics_endpoint_initial_empty_exposition() -> None:
    """Verify that GET /metrics returns standard Prometheus format with zero values."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")

    content = response.text
    assert "# HELP finops_telemetry_ingested_total" in content
    assert "# TYPE finops_telemetry_ingested_total counter" in content
    assert "finops_telemetry_ingested_total 0.0" in content

    assert "# HELP finops_anomalies_detected_total" in content
    assert "# TYPE finops_anomalies_detected_total counter" in content
    assert "finops_anomalies_detected_total 0.0" in content

    assert "# HELP finops_service_cost_amount_gauge" in content
    assert "# TYPE finops_service_cost_amount_gauge gauge" in content
    assert "finops_service_cost_amount_gauge 0.0" in content


def test_metrics_tracked_on_telemetry_ingestion() -> None:
    """Verify that telemetry ingestion increments counters and updates cost gauges."""
    # Ingest 2 records for compute-cluster (EUR)
    client.post(
        "/api/v1/telemetry",
        json={
            "service_name": "compute-cluster",
            "cost_amount": 100.0,
            "currency": "EUR",
        },
    )
    client.post(
        "/api/v1/telemetry",
        json={
            "service_name": "compute-cluster",
            "cost_amount": 120.0,
            "currency": "EUR",
        },
    )

    # Ingest 1 record for object-storage (USD)
    client.post(
        "/api/v1/telemetry",
        json={
            "service_name": "object-storage",
            "cost_amount": 45.5,
            "currency": "USD",
        },
    )

    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text

    # Counters
    assert (
        'finops_telemetry_ingested_total{currency="EUR",service="compute-cluster"} 2.0'
        in content
    )
    assert (
        'finops_telemetry_ingested_total{currency="USD",service="object-storage"} 1.0'
        in content
    )

    # Gauges reflect latest cost
    expected_gauge_cluster = (
        'finops_service_cost_amount_gauge{currency="EUR",'
        'service="compute-cluster"} 120.0'
    )
    assert expected_gauge_cluster in content

    expected_gauge_storage = (
        'finops_service_cost_amount_gauge{currency="USD",'
        'service="object-storage"} 45.5'
    )
    assert expected_gauge_storage in content

    # No anomalies during calibration
    assert "finops_anomalies_detected_total 0.0" in content


def test_metrics_tracked_on_cost_anomaly_spike() -> None:
    """Verify that detected anomalies increment anomaly counter."""
    service = "ai-inference-service"

    # Calibrate with 3 readings of 100.0 EUR
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={"service_name": service, "cost_amount": 100.0, "currency": "EUR"},
        )

    # Trigger anomaly with +50% spike (150.0 EUR)
    response = client.post(
        "/api/v1/telemetry",
        json={"service_name": service, "cost_amount": 150.0, "currency": "EUR"},
    )
    assert response.status_code == 200
    assert response.json()["is_anomaly"] is True

    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    content = metrics_res.text

    assert (
        f'finops_telemetry_ingested_total{{currency="EUR",service="{service}"}} 4.0'
        in content
    )
    assert f'finops_anomalies_detected_total{{service="{service}"}} 1.0' in content
    expected_gauge_spike = (
        f'finops_service_cost_amount_gauge{{currency="EUR",service="{service}"}} 150.0'
    )
    assert expected_gauge_spike in content


def test_metrics_registry_unit_methods() -> None:
    """Verify standalone unit behavior of MetricsRegistry."""
    registry = MetricsRegistry()
    registry.record_telemetry("network-gateway", "EUR", 75.25)
    registry.record_anomaly("network-gateway")

    exposition = registry.generate_prometheus_exposition()
    assert (
        'finops_telemetry_ingested_total{currency="EUR",service="network-gateway"} 1.0'
        in exposition
    )
    assert (
        'finops_anomalies_detected_total{service="network-gateway"} 1.0' in exposition
    )
    expected_unit_gauge = (
        'finops_service_cost_amount_gauge{currency="EUR",'
        'service="network-gateway"} 75.25'
    )
    assert expected_unit_gauge in exposition

    registry.reset()
    clean_exposition = registry.generate_prometheus_exposition()
    assert "finops_telemetry_ingested_total 0.0" in clean_exposition
    assert "finops_anomalies_detected_total 0.0" in clean_exposition
    assert "finops_service_cost_amount_gauge 0.0" in clean_exposition
