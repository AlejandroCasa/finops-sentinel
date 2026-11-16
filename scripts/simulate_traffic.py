"""Traffic simulator generating multi-currency, LLM, and FOCUS telemetry."""

import argparse
import sys
from typing import Any

import httpx


def _simulate_standard_telemetry(
    client: Any, headers: dict[str, str]
) -> tuple[int, int]:
    """Simulate multi-currency standard cost telemetry records."""
    ingested = 0
    anomalies = 0

    scenarios = [
        # EUR calibration + spike
        {
            "service_name": "compute-nodes",
            "cost_amount": 100.0,
            "currency": "EUR",
            "project": "core-infra",
        },
        {
            "service_name": "compute-nodes",
            "cost_amount": 102.0,
            "currency": "EUR",
            "project": "core-infra",
        },
        {
            "service_name": "compute-nodes",
            "cost_amount": 98.0,
            "currency": "EUR",
            "project": "core-infra",
        },
        {
            "service_name": "compute-nodes",
            "cost_amount": 160.0,
            "currency": "EUR",
            "project": "core-infra",
        },
        # USD normal
        {
            "service_name": "object-storage",
            "cost_amount": 50.0,
            "currency": "USD",
            "project": "data-platform",
        },
        {
            "service_name": "object-storage",
            "cost_amount": 52.0,
            "currency": "USD",
            "project": "data-platform",
        },
        {
            "service_name": "object-storage",
            "cost_amount": 51.0,
            "currency": "USD",
            "project": "data-platform",
        },
        # GBP normal
        {
            "service_name": "network-egress",
            "cost_amount": 80.0,
            "currency": "GBP",
            "project": "networking",
        },
        {
            "service_name": "network-egress",
            "cost_amount": 82.0,
            "currency": "GBP",
            "project": "networking",
        },
        {
            "service_name": "network-egress",
            "cost_amount": 81.0,
            "currency": "GBP",
            "project": "networking",
        },
    ]

    for payload in scenarios:
        res = client.post("/api/v1/telemetry", json=payload, headers=headers)
        if res.status_code == 200:
            ingested += 1
            if res.json().get("is_anomaly") is True:
                anomalies += 1

    return ingested, anomalies


def _simulate_llm_telemetry(client: Any, headers: dict[str, str]) -> tuple[int, int]:
    """Simulate LLM token telemetry records and anomaly detection."""
    ingested = 0
    anomalies = 0

    llm_scenarios = [
        # Baseline calibration
        {
            "service_name": "ai-assistant",
            "model": "gpt-4o",
            "input_tokens": 1000,
            "output_tokens": 200,
            "project": "genai",
        },
        {
            "service_name": "ai-assistant",
            "model": "gpt-4o",
            "input_tokens": 1100,
            "output_tokens": 250,
            "project": "genai",
        },
        {
            "service_name": "ai-assistant",
            "model": "gpt-4o",
            "input_tokens": 950,
            "output_tokens": 210,
            "project": "genai",
        },
        # LLM spike
        {
            "service_name": "ai-assistant",
            "model": "gpt-4o",
            "input_tokens": 60000,
            "output_tokens": 15000,
            "project": "genai",
        },
    ]

    for payload in llm_scenarios:
        res = client.post("/api/v1/telemetry/llm", json=payload, headers=headers)
        if res.status_code == 200:
            ingested += 1
            if res.json().get("is_anomaly") is True:
                anomalies += 1

    return ingested, anomalies


def _simulate_focus_telemetry(client: Any, headers: dict[str, str]) -> tuple[int, int]:
    """Simulate FOCUS 1.0 telemetry records and anomaly detection."""
    ingested = 0
    anomalies = 0

    focus_scenarios = [
        # FOCUS calibration
        {
            "ServiceName": "VirtualMachines",
            "BilledCost": 120.0,
            "EffectiveCost": 100.0,
            "RegionId": "eu-west-1",
            "BillingCurrency": "USD",
            "SubAccountId": "enterprise-app",
        },
        {
            "ServiceName": "VirtualMachines",
            "BilledCost": 122.0,
            "EffectiveCost": 102.0,
            "RegionId": "eu-west-1",
            "BillingCurrency": "USD",
            "SubAccountId": "enterprise-app",
        },
        {
            "ServiceName": "VirtualMachines",
            "BilledCost": 118.0,
            "EffectiveCost": 98.0,
            "RegionId": "eu-west-1",
            "BillingCurrency": "USD",
            "SubAccountId": "enterprise-app",
        },
        # FOCUS anomaly spike
        {
            "ServiceName": "VirtualMachines",
            "BilledCost": 300.0,
            "EffectiveCost": 250.0,
            "RegionId": "eu-west-1",
            "BillingCurrency": "USD",
            "SubAccountId": "enterprise-app",
        },
    ]

    for payload in focus_scenarios:
        res = client.post("/api/v1/telemetry/focus", json=payload, headers=headers)
        if res.status_code == 200:
            ingested += 1
            if res.json().get("is_anomaly") is True:
                anomalies += 1

    return ingested, anomalies


def _check_guard_status(
    client: Any, headers: dict[str, str], projects: list[str]
) -> int:
    """Inspect project guard circuit breakers and count blocked projects."""
    blocked = 0
    for project in projects:
        res = client.get(f"/api/v1/guard/{project}", headers=headers)
        if res.status_code == 200 and not res.json().get("allowed", True):
            blocked += 1
    return blocked


def run_simulation(
    client: httpx.Client | Any, api_key: str | None = None
) -> dict[str, int]:
    """Run comprehensive multi-currency, LLM, and FOCUS telemetry simulation."""
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key

    std_ingested, std_anomalies = _simulate_standard_telemetry(client, headers)
    llm_ingested, llm_anomalies = _simulate_llm_telemetry(client, headers)
    focus_ingested, focus_anomalies = _simulate_focus_telemetry(client, headers)

    guard_blocked = _check_guard_status(
        client, headers, ["core-infra", "genai", "enterprise-app", "non-existent"]
    )

    return {
        "ingested": std_ingested + llm_ingested + focus_ingested,
        "anomalies": std_anomalies + llm_anomalies + focus_anomalies,
        "guard_blocked": guard_blocked,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for traffic simulation."""
    parser = argparse.ArgumentParser(
        description="Simulate multi-scenario FinOps traffic."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Target API base URL (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional X-API-Key secret.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute simulation in-process using FastAPI TestClient.",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as test_client:
            summary = run_simulation(test_client, api_key=args.api_key)
    else:
        with httpx.Client(base_url=args.base_url) as http_client:
            summary = run_simulation(http_client, api_key=args.api_key)

    print(f"Simulation completed: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
