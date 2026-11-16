"""Integration and unit tests for batch ingestion, LLM cost calculation,
and webhooks.
"""

import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, detector
from app.metrics import metrics_registry
from app.notifier import WebhookNotifier, webhook_notifier
from app.pricing import calculate_llm_cost
from app.schemas import AnomalyReport

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_environment() -> None:
    """Reset detector, metrics, and application settings before each test."""
    detector.reset()
    metrics_registry.reset()
    webhook_notifier.reset()
    settings.api_key = None
    settings.webhook_url = ""
    settings.webhook_cooldown_seconds = 300


def test_batch_ingestion_success_mixed() -> None:
    """Verify batch ingestion processes multiple records and detects anomalies."""
    records = [
        {
            "service_name": "batch-worker",
            "cost_amount": 100.0,
            "project": "batch-test",
            "environment": "prod",
        },
        {
            "service_name": "batch-worker",
            "cost_amount": 100.0,
            "project": "batch-test",
            "environment": "prod",
        },
        {
            "service_name": "batch-worker",
            "cost_amount": 100.0,
            "project": "batch-test",
            "environment": "prod",
        },
        {
            "service_name": "batch-worker",
            "cost_amount": 200.0,
            "project": "batch-test",
            "environment": "prod",
        },
    ]

    response = client.post("/api/v1/telemetry/batch", json={"records": records})
    assert response.status_code == 200
    data = response.json()

    assert data["total_processed"] == 4
    assert data["anomalies_detected"] == 1
    assert len(data["reports"]) == 4

    # The 4th record should be anomalous (+100% spike over 100.0 mean)
    fourth_report = data["reports"][3]
    assert fourth_report["is_anomaly"] is True
    assert fourth_report["historical_mean"] == pytest.approx(100.0)
    assert fourth_report["deviation_percentage"] == pytest.approx(100.0)
    assert fourth_report["current_cost"] == pytest.approx(200.0)

    # Verify Prometheus exposition updated
    metrics_text = metrics_registry.generate_prometheus_exposition()
    assert (
        'finops_telemetry_ingested_total{currency="EUR",service="batch-worker"} 4.0'
        in metrics_text
    )
    assert 'finops_anomalies_detected_total{service="batch-worker"} 1.0' in metrics_text


def test_batch_ingestion_validation_limits() -> None:
    """Verify batch request enforces min_length=1 and max_length=500."""
    # Empty batch must fail with 422
    res_empty = client.post("/api/v1/telemetry/batch", json={"records": []})
    assert res_empty.status_code == 422

    # Batch exceeding 500 records must fail with 422
    overflow_records = [
        {"service_name": "bulk-svc", "cost_amount": 10.0} for _ in range(501)
    ]
    res_overflow = client.post(
        "/api/v1/telemetry/batch", json={"records": overflow_records}
    )
    assert res_overflow.status_code == 422


def test_batch_ingestion_api_key_auth() -> None:
    """Verify X-API-Key enforcement for batch ingestion endpoint."""
    settings.api_key = "secure-batch-key"
    payload = {
        "records": [
            {"service_name": "auth-svc", "cost_amount": 50.0},
        ]
    }

    # Missing API Key
    res_no_key = client.post("/api/v1/telemetry/batch", json=payload)
    assert res_no_key.status_code == 401

    # Invalid API Key
    res_bad_key = client.post(
        "/api/v1/telemetry/batch",
        headers={"X-API-Key": "wrong-key"},
        json=payload,
    )
    assert res_bad_key.status_code == 401

    # Valid API Key
    res_ok = client.post(
        "/api/v1/telemetry/batch",
        headers={"X-API-Key": "secure-batch-key"},
        json=payload,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["total_processed"] == 1


def test_llm_cost_calculator_known_models() -> None:
    """Verify pricing calculations for all standard supported LLM models."""
    # gpt-4o: 2.50 input, 10.00 output per 1M
    cost_gpt4o = calculate_llm_cost(
        "gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost_gpt4o == pytest.approx(12.50)

    # gpt-4o-mini: 0.15 input, 0.60 output per 1M
    cost_mini = calculate_llm_cost(
        "gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost_mini == pytest.approx(0.75)

    # claude-3-5-sonnet: 3.00 input, 15.00 output per 1M
    cost_sonnet = calculate_llm_cost(
        "claude-3-5-sonnet", input_tokens=100_000, output_tokens=100_000
    )
    assert cost_sonnet == pytest.approx(1.80)

    # claude-3-5-haiku: 0.80 input, 4.00 output per 1M
    cost_haiku = calculate_llm_cost(
        "claude-3-5-haiku", input_tokens=100_000, output_tokens=100_000
    )
    assert cost_haiku == pytest.approx(0.48)

    # gemini-2.5-pro: 1.25 input, 5.00 output per 1M
    cost_gemini_pro = calculate_llm_cost(
        "gemini-2.5-pro", input_tokens=100_000, output_tokens=100_000
    )
    assert cost_gemini_pro == pytest.approx(0.625)

    # gemini-2.5-flash: 0.075 input, 0.30 output per 1M
    cost_gemini_flash = calculate_llm_cost(
        "gemini-2.5-flash", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost_gemini_flash == pytest.approx(0.375)


def test_llm_cost_calculator_fallback() -> None:
    """Verify fallback pricing applies to unlisted/custom models."""
    custom_cost = calculate_llm_cost(
        "custom-fine-tuned-model", input_tokens=1_000_000, output_tokens=1_000_000
    )
    # Default: 1.00 input, 3.00 output -> 4.00
    assert custom_cost == pytest.approx(4.00)


def test_llm_telemetry_endpoint_flow() -> None:
    """Verify POST /api/v1/telemetry/llm ingests token usage and evaluates anomaly."""
    # Ingest 3 baseline requests (e.g. 100k input, 50k output with gpt-4o)
    # 100k * 2.50 / 1M + 50k * 10.00 / 1M = 0.25 + 0.50 = 0.75 USD
    for _ in range(3):
        res = client.post(
            "/api/v1/telemetry/llm",
            json={
                "service_name": "agent-chat",
                "model": "gpt-4o",
                "input_tokens": 100_000,
                "output_tokens": 50_000,
                "project": "ai-platform",
                "environment": "prod",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_anomaly"] is False
        assert data["calculated_cost_usd"] == pytest.approx(0.75)
        assert data["current_cost"] == pytest.approx(0.75)

    # Ingest 4th request with massive token spike (1M output tokens = 10.0 USD)
    spike_res = client.post(
        "/api/v1/telemetry/llm",
        json={
            "service_name": "agent-chat",
            "model": "gpt-4o",
            "input_tokens": 100_000,
            "output_tokens": 1_000_000,
            "project": "ai-platform",
            "environment": "prod",
        },
    )
    assert spike_res.status_code == 200
    spike_data = spike_res.json()
    assert spike_data["is_anomaly"] is True
    # 0.25 + 10.00 = 10.25 USD
    assert spike_data["calculated_cost_usd"] == pytest.approx(10.25)
    assert spike_data["current_cost"] == pytest.approx(10.25)
    assert spike_data["historical_mean"] == pytest.approx(0.75)


def test_llm_telemetry_validation() -> None:
    """Verify token counts must be non-negative and combined tokens strictly > 0."""
    # Zero combined tokens must fail
    res_zero = client.post(
        "/api/v1/telemetry/llm",
        json={
            "service_name": "llm-test",
            "model": "gpt-4o-mini",
            "input_tokens": 0,
            "output_tokens": 0,
        },
    )
    assert res_zero.status_code == 422

    # Negative tokens must fail
    res_neg = client.post(
        "/api/v1/telemetry/llm",
        json={
            "service_name": "llm-test",
            "model": "gpt-4o-mini",
            "input_tokens": -5,
            "output_tokens": 100,
        },
    )
    assert res_neg.status_code == 422


def test_llm_telemetry_api_key_auth() -> None:
    """Verify X-API-Key security for LLM telemetry endpoint."""
    settings.api_key = "secret-llm-token"
    payload = {
        "service_name": "agent-auth",
        "model": "gemini-2.5-flash",
        "input_tokens": 1000,
        "output_tokens": 2000,
    }

    # Missing API Key
    res_no = client.post("/api/v1/telemetry/llm", json=payload)
    assert res_no.status_code == 401

    # Valid API Key
    res_ok = client.post(
        "/api/v1/telemetry/llm",
        headers={"X-API-Key": "secret-llm-token"},
        json=payload,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["service_name"] == "agent-auth"


def test_webhook_dispatch_on_anomaly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify push webhook is dispatched when an anomaly is detected."""
    settings.webhook_url = "https://hooks.slack.com/services/T00/B00/X00"
    dispatched_requests: list[urllib.request.Request] = []

    class MockHTTPResponse:
        status = 200

        def __enter__(self) -> "MockHTTPResponse":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    def mock_urlopen(
        req: urllib.request.Request, timeout: float = 3.0
    ) -> MockHTTPResponse:
        dispatched_requests.append(req)
        return MockHTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Establish baseline
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={
                "service_name": "payment-api",
                "cost_amount": 100.0,
                "project": "fintech",
            },
        )
    assert len(dispatched_requests) == 0

    # Trigger anomaly
    client.post(
        "/api/v1/telemetry",
        json={
            "service_name": "payment-api",
            "cost_amount": 250.0,
            "project": "fintech",
        },
    )
    assert len(dispatched_requests) == 1
    req = dispatched_requests[0]
    assert req.full_url == "https://hooks.slack.com/services/T00/B00/X00"
    assert req.get_header("Content-type") == "application/json"

    assert isinstance(req.data, bytes)
    body = json.loads(req.data.decode("utf-8"))
    assert body["service_name"] == "payment-api"
    assert body["project"] == "fintech"
    assert body["current_cost"] == 250.0
    assert body["deviation_percentage"] == pytest.approx(150.0)


def test_webhook_anti_spam_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify repeated anomalies within the cooldown window do not spam webhooks."""
    settings.webhook_url = "https://hooks.teams.microsoft.com/webhookb2/test"
    settings.webhook_cooldown_seconds = 300
    call_count = 0

    class MockHTTPResponse:
        status = 200

        def __enter__(self) -> "MockHTTPResponse":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    def mock_urlopen(
        req: urllib.request.Request, timeout: float = 3.0
    ) -> MockHTTPResponse:
        nonlocal call_count
        call_count += 1
        return MockHTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Baseline for service A and service B
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={"service_name": "service-a", "cost_amount": 100.0},
        )
        client.post(
            "/api/v1/telemetry",
            json={"service_name": "service-b", "cost_amount": 100.0},
        )

    # First anomaly for service A -> dispatched
    client.post(
        "/api/v1/telemetry",
        json={"service_name": "service-a", "cost_amount": 200.0},
    )
    assert call_count == 1

    # Second anomaly for service A immediately -> suppressed by anti-spam cooldown!
    client.post(
        "/api/v1/telemetry",
        json={"service_name": "service-a", "cost_amount": 220.0},
    )
    assert call_count == 1

    # Anomaly for different service B -> dispatched (independent tuple cooldown)
    client.post(
        "/api/v1/telemetry",
        json={"service_name": "service-b", "cost_amount": 250.0},
    )
    assert call_count == 2


def test_webhook_network_error_gracefully_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify network exceptions in webhook dispatch do not fail telemetry ingestion."""
    settings.webhook_url = "https://unreachable-endpoint.local/webhook"

    def mock_urlopen_error(req: urllib.request.Request, timeout: float = 3.0) -> Any:
        raise urllib.error.URLError("Connection timed out")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen_error)

    # Calibration
    for _ in range(3):
        client.post(
            "/api/v1/telemetry",
            json={"service_name": "robust-svc", "cost_amount": 100.0},
        )

    # Anomaly with network failure
    res = client.post(
        "/api/v1/telemetry",
        json={"service_name": "robust-svc", "cost_amount": 300.0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_anomaly"] is True
    assert data["current_cost"] == 300.0


def test_webhook_notifier_unit_edge_cases() -> None:
    """Verify WebhookNotifier edge cases: invalid protocols, empty URLs, and resets."""
    notifier = WebhookNotifier()
    report = AnomalyReport(
        is_anomaly=True,
        deviation_percentage=50.0,
        current_cost=150.0,
        historical_mean=100.0,
        service_name="test-svc",
    )

    # Empty URL returns False
    assert notifier.send_alert(report, webhook_url="") is False

    # Invalid protocol returns False
    assert notifier.send_alert(report, webhook_url="ftp://invalid.com") is False
    assert notifier.send_alert(report, webhook_url="javascript:alert(1)") is False

    # Reset clears cooldown dictionary
    notifier.reset()
    assert len(notifier._last_alert_time) == 0
