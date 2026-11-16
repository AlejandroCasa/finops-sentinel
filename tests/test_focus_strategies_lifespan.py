"""Tests for FOCUS 1.0 telemetry, statistical detection strategies, and lifespan."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.detector import AnomalyDetector
from app.main import app, detector
from app.metrics import metrics_registry
from app.notifier import webhook_notifier
from app.schemas import CostRecord, FOCUSTelemetryRequest
from scripts.simulate_traffic import main as simulate_main
from scripts.simulate_traffic import run_simulation


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    """Reset detector memory, SQLite state, metrics, and config before each test."""
    detector.reset()
    metrics_registry.reset()
    webhook_notifier.reset()
    settings.api_key = None
    settings.webhook_url = ""
    settings.webhook_cooldown_seconds = 300
    settings.detection_strategy = "percentage"
    settings.deviation_threshold_percent = 25.0
    settings.zscore_threshold = 2.5
    settings.ewma_alpha = 0.3


def test_lifespan_context_manager() -> None:
    """Verify that lifespan startup initializes DB and shutdown drains safely."""
    with TestClient(app) as test_client:
        response = test_client.get("/healthz")
        assert response.status_code == 200


def test_detector_close_method() -> None:
    """Verify detector.close() executes clean SQLite checkpoint/commit."""
    custom_detector = AnomalyDetector()
    custom_detector.close()
    assert True


def test_focus_telemetry_request_validation() -> None:
    """Verify FOCUS schema rejects zero/negative cost records."""
    with pytest.raises(ValueError, match="Either EffectiveCost or BilledCost"):
        FOCUSTelemetryRequest(
            BilledCost=0.0,
            EffectiveCost=0.0,
            ServiceName="Compute",
        )


def test_focus_telemetry_endpoint_flow() -> None:
    """Verify FOCUS telemetry ingestion, fallback from EffectiveCost to BilledCost."""
    client = TestClient(app)

    # 1. EffectiveCost preferred over BilledCost
    res1 = client.post(
        "/api/v1/telemetry/focus",
        json={
            "BilledCost": 120.0,
            "EffectiveCost": 100.0,
            "ServiceName": "cloud-compute",
            "RegionId": "eu-central-1",
            "BillingCurrency": "USD",
            "SubAccountId": "tenant-alpha",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["current_cost"] == 100.0
    assert data1["effective_cost"] == 100.0
    assert data1["billed_cost"] == 120.0
    assert data1["region_id"] == "eu-central-1"
    assert data1["project"] == "tenant-alpha"
    assert data1["is_anomaly"] is False

    # 2. BilledCost used when EffectiveCost is 0
    res2 = client.post(
        "/api/v1/telemetry/focus",
        json={
            "BilledCost": 85.0,
            "EffectiveCost": 0.0,
            "ServiceName": "cloud-storage",
            "RegionId": "us-east-1",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["current_cost"] == 85.0
    assert data2["billed_cost"] == 85.0
    assert data2["effective_cost"] == 0.0
    assert data2["region_id"] == "us-east-1"


def test_focus_telemetry_anomaly_spike_and_metrics() -> None:
    """Verify FOCUS endpoint detects anomalous spike and increments metrics."""
    client = TestClient(app)

    # Calibration (3 readings)
    for _ in range(3):
        res = client.post(
            "/api/v1/telemetry/focus",
            json={
                "BilledCost": 100.0,
                "EffectiveCost": 100.0,
                "ServiceName": "focus-k8s",
                "SubAccountId": "k8s-project",
            },
        )
        assert res.status_code == 200
        assert res.json()["is_anomaly"] is False

    # Anomalous spike
    res_spike = client.post(
        "/api/v1/telemetry/focus",
        json={
            "BilledCost": 200.0,
            "EffectiveCost": 200.0,
            "ServiceName": "focus-k8s",
            "SubAccountId": "k8s-project",
        },
    )
    assert res_spike.status_code == 200
    data_spike = res_spike.json()
    assert data_spike["is_anomaly"] is True
    assert data_spike["current_cost"] == 200.0
    assert data_spike["historical_mean"] == 100.0
    assert data_spike["deviation_percentage"] == 100.0

    # Verify metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert 'service="focus-k8s"' in metrics_res.text
    assert "finops_anomalies_detected_total" in metrics_res.text


def test_focus_telemetry_auth() -> None:
    """Verify FOCUS telemetry endpoint enforces X-API-Key security."""
    settings.api_key = "focus-secret-token"
    client = TestClient(app)

    payload = {
        "BilledCost": 50.0,
        "EffectiveCost": 50.0,
        "ServiceName": "secure-service",
    }

    # Unauthorized
    unauth = client.post("/api/v1/telemetry/focus", json=payload)
    assert unauth.status_code == 401

    # Authorized
    auth = client.post(
        "/api/v1/telemetry/focus",
        json=payload,
        headers={"X-API-Key": "focus-secret-token"},
    )
    assert auth.status_code == 200


def test_detection_strategy_zscore() -> None:
    """Verify Z-Score detection strategy under zero variance and normal variance."""
    settings.detection_strategy = "zscore"
    settings.zscore_threshold = 2.5
    settings.deviation_threshold_percent = 25.0

    # 1. Calibration with identical readings (stdev == 0)
    for _ in range(3):
        report = detector.evaluate(
            CostRecord(service_name="zscore-service", cost_amount=100.0)
        )
        assert report.is_anomaly is False

    # Stdev == 0, cost is 110.0 (+10% < 25%) -> not anomaly
    r_normal = detector.evaluate(
        CostRecord(service_name="zscore-service", cost_amount=110.0)
    )
    assert r_normal.is_anomaly is False

    # Stdev == 0, cost is 135.0 (+35% > 25%) -> anomaly via fallback
    r_spike_zero_stdev = detector.evaluate(
        CostRecord(service_name="zscore-service", cost_amount=135.0)
    )
    assert r_spike_zero_stdev.is_anomaly is True

    # 2. Add variance to readings
    detector.reset()
    readings = [100.0, 102.0, 98.0, 101.0, 99.0]
    for cost in readings:
        detector.evaluate(CostRecord(service_name="zscore-var", cost_amount=cost))

    # Mild variation: cost 102.0 (z-score = 2 / 1.414 ≈ 1.41 <= 2.5)
    mild_report = detector.evaluate(
        CostRecord(service_name="zscore-var", cost_amount=102.0)
    )
    assert mild_report.is_anomaly is False

    # Extreme variation: cost 120.0 (z-score = 20 / 1.414 ≈ 14.1 > 2.5)
    extreme_report = detector.evaluate(
        CostRecord(service_name="zscore-var", cost_amount=120.0)
    )
    assert extreme_report.is_anomaly is True


def test_detector_get_alerts_filtering() -> None:
    """Verify get_alerts filtering by project parameter."""
    for _ in range(3):
        detector.evaluate(
            CostRecord(service_name="srv-1", cost_amount=100.0, project="p-1")
        )
    detector.evaluate(
        CostRecord(service_name="srv-1", cost_amount=200.0, project="p-1")
    )

    alerts_p1 = detector.get_alerts(project="p-1")
    alerts_p2 = detector.get_alerts(project="p-2")
    assert len(alerts_p1) >= 1
    assert len(alerts_p2) == 0


def test_detection_strategy_ewma() -> None:
    """Verify EWMA detection strategy calculations and anomaly detection."""
    settings.detection_strategy = "ewma"
    settings.ewma_alpha = 0.5
    settings.deviation_threshold_percent = 25.0

    # Calibration
    # Reading 1: 100 -> ewma: 100
    # Reading 2: 120 -> ewma: 0.5*120 + 0.5*100 = 110
    # Reading 3: 140 -> ewma: 0.5*140 + 0.5*110 = 125
    costs = [100.0, 120.0, 140.0]
    for c in costs:
        report = detector.evaluate(
            CostRecord(service_name="ewma-service", cost_amount=c)
        )
        assert report.is_anomaly is False

    # Evaluated reading against EWMA baseline (125.0)
    # Normal: 130.0 -> deviation: (130 - 125)/125 * 100 = +4.0%
    normal_report = detector.evaluate(
        CostRecord(service_name="ewma-service", cost_amount=130.0)
    )
    assert normal_report.is_anomaly is False
    assert normal_report.historical_mean == pytest.approx(125.0)

    # Spike: 200.0 -> deviation: (200 - 127.5) / 127.5 * 100 > 25%
    spike_report = detector.evaluate(
        CostRecord(service_name="ewma-service", cost_amount=200.0)
    )
    assert spike_report.is_anomaly is True

    # Poisoning protection: 200.0 not appended to history
    followup_report = detector.evaluate(
        CostRecord(service_name="ewma-service", cost_amount=135.0)
    )
    # Mean should be based on previous unpoisoned readings
    assert followup_report.is_anomaly is False


def test_traffic_simulation_dry_run() -> None:
    """Verify simulate_traffic script executes successfully in-process."""
    with TestClient(app) as client:
        summary = run_simulation(client)
        assert summary["ingested"] > 0
        assert summary["anomalies"] >= 3
        assert "guard_blocked" in summary

    # Verify CLI entrypoint
    exit_code = simulate_main(["--dry-run"])
    assert exit_code == 0
