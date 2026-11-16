"""Integration and unit tests for FinOps Sentinel multi-tenant anomaly detection."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.detector import AnomalyDetector
from app.main import app, detector
from app.schemas import CostRecord

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_detector_state() -> None:
    """Ensure detector memory and SQLite state is reset before each test."""
    detector.reset()
    settings.api_key = None


def test_healthz_endpoint() -> None:
    """Verify that GET /healthz returns 200 OK for Kubernetes probes."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_calibration_period_does_not_trigger_anomaly() -> None:
    """Verify that fewer than 3 prior readings never trigger an anomaly."""
    calibration_costs = [100.0, 150.0, 200.0]
    for cost in calibration_costs:
        response = client.post(
            "/api/v1/telemetry",
            json={"service_name": "cloud-storage", "cost_amount": cost},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is False
        assert data["service_name"] == "cloud-storage"
        assert data["current_cost"] == cost
        assert data["project"] == "default"
        assert data["environment"] == "prod"


def test_normal_variation_does_not_trigger_anomaly() -> None:
    """Verify that a +5% variation after calibration does not trigger an anomaly."""
    for _ in range(3):
        res = client.post(
            "/api/v1/telemetry",
            json={"service_name": "compute-cluster", "cost_amount": 100.0},
        )
        assert res.status_code == 200
        assert res.json()["is_anomaly"] is False

    response = client.post(
        "/api/v1/telemetry",
        json={"service_name": "compute-cluster", "cost_amount": 105.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is False
    assert data["historical_mean"] == pytest.approx(100.0)
    assert data["deviation_percentage"] == pytest.approx(5.0)
    assert data["current_cost"] == pytest.approx(105.0)


def test_anomalous_spike_triggers_anomaly_and_calculates_deviation() -> None:
    """Verify that a +50% cost spike triggers an anomaly with accurate deviation."""
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={"service_name": "compute-cluster", "cost_amount": 100.0},
        )

    response = client.post(
        "/api/v1/telemetry",
        json={"service_name": "compute-cluster", "cost_amount": 150.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["historical_mean"] == pytest.approx(100.0)
    assert data["deviation_percentage"] == pytest.approx(50.0)
    assert data["current_cost"] == pytest.approx(150.0)
    assert data["service_name"] == "compute-cluster"


def test_alerts_endpoint_persists_detected_anomalies() -> None:
    """Verify that GET /api/v1/alerts returns persisted anomaly reports."""
    for cost in [200.0, 200.0, 200.0, 300.0]:
        client.post(
            "/api/v1/telemetry",
            json={
                "service_name": "managed-db",
                "cost_amount": cost,
                "project": "ecommerce",
            },
        )

    response = client.get("/api/v1/alerts?project=ecommerce")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["is_anomaly"] is True
    assert alerts[0]["project"] == "ecommerce"
    assert alerts[0]["service_name"] == "managed-db"


def test_baseline_poisoning_protection() -> None:
    """Verify anomalous readings do not inflate the historical mean baseline."""
    service = "api-gateway"
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={"service_name": service, "cost_amount": 100.0},
        )

    anomaly_res = client.post(
        "/api/v1/telemetry",
        json={"service_name": service, "cost_amount": 200.0},
    )
    assert anomaly_res.status_code == 200
    assert anomaly_res.json()["is_anomaly"] is True

    subsequent_res = client.post(
        "/api/v1/telemetry",
        json={"service_name": service, "cost_amount": 120.0},
    )
    assert subsequent_res.status_code == 200
    data = subsequent_res.json()
    assert data["historical_mean"] == pytest.approx(100.0)
    assert data["deviation_percentage"] == pytest.approx(20.0)
    assert data["is_anomaly"] is False
    # History must contain 3 baseline readings plus 1 normal reading (no anomaly)
    key = ("default", "prod", service)
    assert len(detector.history[key]) == 4
    assert 200.0 not in detector.history[key]


def test_multi_tenant_isolation() -> None:
    """Verify that project A readings do not pollute project B baseline."""
    # Establish project-alpha baseline at 100 EUR
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={
                "project": "alpha",
                "environment": "prod",
                "service_name": "ai-worker",
                "cost_amount": 100.0,
            },
        )

    # Establish project-beta baseline at 500 EUR
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={
                "project": "beta",
                "environment": "prod",
                "service_name": "ai-worker",
                "cost_amount": 500.0,
            },
        )

    # Ingest 150 EUR for alpha (+50% spike for alpha)
    res_alpha = client.post(
        "/api/v1/telemetry",
        json={
            "project": "alpha",
            "environment": "prod",
            "service_name": "ai-worker",
            "cost_amount": 150.0,
        },
    )
    assert res_alpha.status_code == 200
    assert res_alpha.json()["is_anomaly"] is True
    assert res_alpha.json()["historical_mean"] == pytest.approx(100.0)

    # Ingest 520 EUR for beta (normal +4% for beta)
    res_beta = client.post(
        "/api/v1/telemetry",
        json={
            "project": "beta",
            "environment": "prod",
            "service_name": "ai-worker",
            "cost_amount": 520.0,
        },
    )
    assert res_beta.status_code == 200
    assert res_beta.json()["is_anomaly"] is False
    assert res_beta.json()["historical_mean"] == pytest.approx(500.0)


def test_sqlite_persistence_across_instances() -> None:
    """Verify readings and alerts persist in SQLite across instances."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        det1 = AnomalyDetector(db_path=db_path)
        record = CostRecord(
            service_name="blob-storage",
            cost_amount=50.0,
            project="analytics",
            environment="staging",
            owner_team="data",
        )
        det1.evaluate(record)

        # Inspect second instance with same DB file
        det2 = AnomalyDetector(db_path=db_path)
        guard = det2.get_guard_status("analytics")
        assert guard.total_cost == pytest.approx(50.0)
        assert guard.allowed is True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_api_key_security() -> None:
    """Verify X-API-Key header enforcement when configured."""
    settings.api_key = "secret-token-123"

    # Missing API Key
    res_unauth = client.get("/api/v1/alerts")
    assert res_unauth.status_code == 401

    # Invalid API Key
    res_bad = client.get(
        "/api/v1/alerts",
        headers={"X-API-Key": "wrong-token"},
    )
    assert res_bad.status_code == 401

    # Valid API Key
    res_ok = client.get(
        "/api/v1/alerts",
        headers={"X-API-Key": "secret-token-123"},
    )
    assert res_ok.status_code == 200


def test_circuit_breaker_guard_endpoint() -> None:
    """Verify guard allows or blocks execution based on budget limits."""
    project = "fintech-core"
    guard_res = client.get(f"/api/v1/guard/{project}")
    assert guard_res.status_code == 200
    assert guard_res.json()["allowed"] is True

    # Simulate excessive spend exceeding budget_default_limit (1000.0)
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={
                "project": project,
                "service_name": "ledger-db",
                "cost_amount": 400.0,
            },
        )

    blocked_res = client.get(f"/api/v1/guard/{project}")
    assert blocked_res.status_code == 200
    data = blocked_res.json()
    assert data["allowed"] is False
    assert "exceeds hard budget" in data["reason"]
