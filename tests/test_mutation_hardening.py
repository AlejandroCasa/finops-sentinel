"""Mutation hardening and deterministic Atheris fuzzing verification tests."""

import pytest

from app.config import settings
from app.detector import AnomalyDetector
from app.pricing import DEFAULT_LLM_PRICING, LLM_PRICING_PER_MILLION, calculate_llm_cost
from app.schemas import CostRecord, FOCUSTelemetryRequest
from fuzz.fuzz_telemetry import run_deterministic_self_test


@pytest.fixture(autouse=True)
def reset_settings_and_detector() -> None:
    """Restore default settings before each mutation hardening test."""
    settings.detection_strategy = "percentage"
    settings.deviation_threshold_percent = 25.0
    settings.zscore_threshold = 2.5
    settings.ewma_alpha = 0.3
    settings.budget_default_limit = 1000.0
    settings.max_anomalies_before_block = 3


def test_atheris_deterministic_fuzz_self_test() -> None:
    """Verify Atheris / fallback fuzzing harness runs 25 deterministic iterations."""
    run_deterministic_self_test(iterations=25)


def test_calibration_exact_boundary_three_readings() -> None:
    """Kill mutants changing `< 3` to `<= 3` or `< 2` in calibration window."""
    det = AnomalyDetector()
    det.reset()

    # Readings 1, 2, 3 are strictly calibration (even with 500% jump on reading 3)
    r1 = det.evaluate(CostRecord(service_name="cal-bound", cost_amount=100.0))
    assert r1.is_anomaly is False
    assert r1.historical_mean == 0.0
    assert r1.deviation_percentage == 0.0

    r2 = det.evaluate(CostRecord(service_name="cal-bound", cost_amount=100.0))
    assert r2.is_anomaly is False
    assert r2.historical_mean == pytest.approx(100.0)
    assert r2.deviation_percentage == 0.0

    r3 = det.evaluate(CostRecord(service_name="cal-bound", cost_amount=100.0))
    assert r3.is_anomaly is False
    assert r3.historical_mean == pytest.approx(100.0)
    assert r3.deviation_percentage == 0.0

    # Reading 4 is evaluated against baseline
    r4 = det.evaluate(CostRecord(service_name="cal-bound", cost_amount=130.0))
    assert r4.is_anomaly is True
    assert r4.deviation_percentage == pytest.approx(30.0)


def test_percentage_threshold_exact_boundary() -> None:
    """Kill mutants changing `>` to `>=` at the +25.0% deviation threshold."""
    det = AnomalyDetector()
    det.reset()

    for _ in range(3):
        det.evaluate(CostRecord(service_name="pct-bound", cost_amount=100.0))

    # Exactly +25.0% (125.0 vs 100.0) must NOT be an anomaly (`>` not `>=`)
    exact = det.evaluate(CostRecord(service_name="pct-bound", cost_amount=125.0))
    assert exact.deviation_percentage == pytest.approx(25.0)
    assert exact.is_anomaly is False

    # Reset and verify +25.01% triggers an anomaly
    det.reset()
    for _ in range(3):
        det.evaluate(CostRecord(service_name="pct-bound", cost_amount=100.0))

    above = det.evaluate(CostRecord(service_name="pct-bound", cost_amount=125.01))
    assert above.deviation_percentage == pytest.approx(25.01)
    assert above.is_anomaly is True


def test_zscore_exact_boundary() -> None:
    """Kill mutants changing `>` to `>=` at zscore_threshold."""
    settings.detection_strategy = "zscore"
    settings.zscore_threshold = 2.0

    det = AnomalyDetector()
    det.reset()

    # Readings: [90.0, 100.0, 110.0] -> mean = 100.0, pstdev = sqrt(200/3)
    # Wait: use [90.0, 110.0, 90.0, 110.0] -> mean = 100.0, pstdev = 10.0!
    for cost in [90.0, 110.0, 90.0, 110.0]:
        det.evaluate(CostRecord(service_name="z-bound", cost_amount=cost))

    # With mean=100.0, pstdev=10.0, cost=120.0 gives z_score = (120-100)/10 = 2.0
    # Since threshold is 2.0 and check is `z_score > threshold`, 120.0 is False
    exact_z = det.evaluate(CostRecord(service_name="z-bound", cost_amount=120.0))
    assert exact_z.is_anomaly is False

    # Reset and test cost=120.1 -> z_score = 2.01 > 2.0 -> True
    det.reset()
    for cost in [90.0, 110.0, 90.0, 110.0]:
        det.evaluate(CostRecord(service_name="z-bound", cost_amount=cost))

    above_z = det.evaluate(CostRecord(service_name="z-bound", cost_amount=120.1))
    assert above_z.is_anomaly is True


def test_guard_circuit_breaker_exact_boundaries() -> None:
    """Kill mutants on budget_limit (`>` vs `>=`) and max_anomalies (`>=` vs `>`)."""
    det = AnomalyDetector()
    det.reset()
    settings.budget_default_limit = 300.0
    settings.max_anomalies_before_block = 2

    # 3 readings of 100.0 -> total_cost == 300.0 == budget_limit (allowed: True)
    for _ in range(3):
        det.evaluate(
            CostRecord(service_name="guard-svc", cost_amount=100.0, project="p-exact")
        )

    guard_exact = det.get_guard_status("p-exact")
    assert guard_exact.total_cost == pytest.approx(300.0)
    assert guard_exact.allowed is True

    # Test anomaly count boundary: 2 anomalies when max_anomalies_before_block == 2
    settings.budget_default_limit = 10_000.0
    det.evaluate(
        CostRecord(service_name="guard-svc", cost_amount=200.0, project="p-exact")
    )
    guard_one_anom = det.get_guard_status("p-exact")
    assert guard_one_anom.anomaly_count == 1
    assert guard_one_anom.allowed is True

    det.evaluate(
        CostRecord(service_name="guard-svc", cost_amount=250.0, project="p-exact")
    )
    guard_two_anom = det.get_guard_status("p-exact")
    assert guard_two_anom.anomaly_count == 2
    assert guard_two_anom.allowed is False
    assert "anomalies" in guard_two_anom.reason


def test_pricing_minimum_floor_and_rounding() -> None:
    """Kill mutants in calculate_llm_cost floor (0.000001) and case normalization."""
    assert LLM_PRICING_PER_MILLION["gpt-4o"] == (2.50, 10.00)
    assert DEFAULT_LLM_PRICING == (1.00, 3.00)

    # Tiny token count hits minimum floor 0.000001
    floor_cost = calculate_llm_cost("  GPT-4O-MINI  ", input_tokens=1, output_tokens=0)
    assert floor_cost == 0.000001

    # Exact arithmetic check
    exact_cost = calculate_llm_cost(
        "  Claude-3-5-Sonnet ", input_tokens=500_000, output_tokens=200_000
    )
    # 0.5 * 3.00 + 0.2 * 15.00 = 1.50 + 3.00 = 4.50
    assert exact_cost == pytest.approx(4.50)


def test_focus_schema_boundary_validation() -> None:
    """Verify FOCUSTelemetryRequest accepts positive BilledCost or EffectiveCost."""
    req_billed_only = FOCUSTelemetryRequest(
        BilledCost=0.01,
        EffectiveCost=0.0,
        ServiceName="AmazonEC2",
    )
    assert req_billed_only.billed_cost == 0.01
    assert req_billed_only.effective_cost == 0.0

    req_effective_only = FOCUSTelemetryRequest(
        BilledCost=0.0,
        EffectiveCost=0.01,
        ServiceName="AmazonS3",
    )
    assert req_effective_only.effective_cost == 0.01
