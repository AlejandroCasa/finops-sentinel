"""Integration and unit tests for FinOps Sentinel anomaly detection endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, detector

client = TestClient(app)


def test_calibration_period_does_not_trigger_anomaly() -> None:
    """Verify that fewer than 3 prior readings never trigger an anomaly."""
    detector.history.clear()
    detector.alerts.clear()

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


def test_normal_variation_does_not_trigger_anomaly() -> None:
    """Verify that a +5% variation after calibration does not trigger an anomaly."""
    detector.history.clear()
    detector.alerts.clear()

    # Ingest 3 baseline readings of 100.0 EUR
    for _ in range(3):
        response = client.post(
            "/api/v1/telemetry",
            json={"service_name": "compute-cluster", "cost_amount": 100.0},
        )
        assert response.status_code == 200
        assert response.json()["is_anomaly"] is False

    # 4th reading with +5% variation (105.0 EUR)
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
    detector.history.clear()
    detector.alerts.clear()

    # Ingest 3 baseline readings of 100.0 EUR
    for _ in range(3):
        response = client.post(
            "/api/v1/telemetry",
            json={"service_name": "compute-cluster", "cost_amount": 100.0},
        )
        assert response.status_code == 200

    # 4th reading with +50% spike (150.0 EUR)
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
    detector.history.clear()
    detector.alerts.clear()

    # Calibrate with 3 baseline readings and trigger 1 anomaly (+50%)
    for cost in [200.0, 200.0, 200.0, 300.0]:
        client.post(
            "/api/v1/telemetry",
            json={"service_name": "managed-db", "cost_amount": cost},
        )

    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["is_anomaly"] is True
    assert alert["service_name"] == "managed-db"
    assert alert["historical_mean"] == pytest.approx(200.0)
    assert alert["current_cost"] == pytest.approx(300.0)
    assert alert["deviation_percentage"] == pytest.approx(50.0)
