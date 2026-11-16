"""Coverage-guided Atheris fuzzing harness for FinOps Sentinel telemetry engine."""

import atexit
import contextlib
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Protocol

try:
    import atheris

    _instrument = atheris.instrument_imports()
except (ImportError, AttributeError):
    atheris: Any = None  # type: ignore[no-redef]
    _instrument = contextlib.nullcontext()

with _instrument:
    from pydantic import ValidationError

    from app.detector import AnomalyDetector
    from app.pricing import calculate_llm_cost
    from app.schemas import CostRecord, LLMTelemetryRequest


class _DataProviderProtocol(Protocol):
    """Protocol defining the subset of FuzzedDataProvider methods used."""

    def remaining_bytes(self) -> int: ...

    def ConsumeBytes(self, count: int) -> bytes: ...  # noqa: N802

    def ConsumeIntInRange(self, min_val: int, max_val: int) -> int: ...  # noqa: N802

    def ConsumeFloatInRange(  # noqa: N802
        self, min_val: float, max_val: float
    ) -> float: ...

    def ConsumeFloat(self) -> float: ...  # noqa: N802

    def ConsumeBool(self) -> bool: ...  # noqa: N802

    def ConsumeUnicodeNoSurrogates(self, count: int) -> str: ...  # noqa: N802


class _FallbackDataProvider:
    """Lightweight deterministic fallback for Atheris FuzzedDataProvider."""

    def __init__(self, data: bytes) -> None:
        self._data: bytes = data
        self._pos: int = 0

    def remaining_bytes(self) -> int:
        """Return the count of unconsumed bytes."""
        return max(0, len(self._data) - self._pos)

    def ConsumeBytes(self, count: int) -> bytes:  # noqa: N802
        """Consume up to count raw bytes from the buffer."""
        if self._pos >= len(self._data) or count <= 0:
            return b""
        end = min(len(self._data), self._pos + count)
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def ConsumeIntInRange(self, min_val: int, max_val: int) -> int:  # noqa: N802
        """Consume an integer uniformly bounded within [min_val, max_val]."""
        if min_val >= max_val:
            return min_val
        span = max_val - min_val + 1
        raw = self.ConsumeBytes(4)
        if not raw:
            return min_val
        val = int.from_bytes(raw, byteorder="little", signed=False)
        return min_val + (val % span)

    def ConsumeFloatInRange(  # noqa: N802
        self, min_val: float, max_val: float
    ) -> float:
        """Consume a float uniformly bounded within [min_val, max_val]."""
        if min_val >= max_val:
            return min_val
        raw = self.ConsumeBytes(4)
        if not raw:
            return min_val
        int_val = int.from_bytes(raw, byteorder="little", signed=False)
        ratio = int_val / 0xFFFFFFFF
        return min_val + ratio * (max_val - min_val)

    def ConsumeFloat(self) -> float:  # noqa: N802
        """Consume an arbitrary floating point value."""
        return self.ConsumeFloatInRange(-1e6, 1e6)

    def ConsumeBool(self) -> bool:  # noqa: N802
        """Consume a single boolean flag."""
        raw = self.ConsumeBytes(1)
        if not raw:
            return False
        return (raw[0] % 2) == 1

    def ConsumeUnicodeNoSurrogates(self, count: int) -> str:  # noqa: N802
        """Consume a valid UTF-8 string without unicode surrogates."""
        raw = self.ConsumeBytes(count)
        decoded = raw.decode("utf-8", errors="replace")
        return decoded.replace("\ud800", "").replace("\udfff", "")


def _get_data_provider(data: bytes) -> _DataProviderProtocol:
    """Return an Atheris FuzzedDataProvider or fallback instance."""
    if atheris is not None:
        provider: _DataProviderProtocol = atheris.FuzzedDataProvider(data)
        return provider
    return _FallbackDataProvider(data)


_FUZZ_TEMP_DIR: str | None = None
_GLOBAL_DETECTOR: AnomalyDetector | None = None


def _cleanup_fuzz_temp_dir() -> None:
    """Safely remove the temporary SQLite directory on module unload."""
    global _FUZZ_TEMP_DIR
    if _FUZZ_TEMP_DIR is not None and os.path.exists(_FUZZ_TEMP_DIR):
        shutil.rmtree(_FUZZ_TEMP_DIR, ignore_errors=True)


def _get_fuzz_detector() -> AnomalyDetector:
    """Return a singleton AnomalyDetector backed by an isolated temporary DB."""
    global _FUZZ_TEMP_DIR, _GLOBAL_DETECTOR
    if _GLOBAL_DETECTOR is None:
        if _FUZZ_TEMP_DIR is None:
            _FUZZ_TEMP_DIR = tempfile.mkdtemp(prefix="finops_sentinel_fuzz_")
            atexit.register(_cleanup_fuzz_temp_dir)
        db_path = str(Path(_FUZZ_TEMP_DIR) / "fuzz_telemetry.db")
        _GLOBAL_DETECTOR = AnomalyDetector(db_path=db_path)
    return _GLOBAL_DETECTOR


def _fuzz_pricing_calculator(fdp: _DataProviderProtocol) -> None:
    """Fuzz calculate_llm_cost across arbitrary models and token bounds."""
    if fdp.ConsumeBool():
        known_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet",
            "claude-3-5-haiku",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ]
        model = known_models[fdp.ConsumeIntInRange(0, len(known_models) - 1)]
    else:
        model = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 40))

    input_tokens = fdp.ConsumeIntInRange(-5000, 10_000_000)
    output_tokens = fdp.ConsumeIntInRange(-5000, 10_000_000)

    cost = calculate_llm_cost(model, input_tokens, output_tokens)

    assert cost >= 0.000001, f"Calculated cost {cost} must be >= 0.000001"
    assert not math.isnan(cost), f"Calculated cost must not be NaN: {cost}"
    assert not math.isinf(cost), f"Calculated cost must not be infinite: {cost}"


def _fuzz_schema_validation(fdp: _DataProviderProtocol) -> None:
    """Fuzz CostRecord and LLMTelemetryRequest schema validation."""
    svc = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 30))
    cost = fdp.ConsumeFloatInRange(-500.0, 50_000.0)
    curr = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 6))
    proj = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 20))
    env = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 15))
    team = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 20))
    sha = fdp.ConsumeUnicodeNoSurrogates(40) if fdp.ConsumeBool() else None

    try:
        record = CostRecord(
            service_name=svc,
            cost_amount=cost,
            currency=curr or "EUR",
            project=proj or "default",
            environment=env or "prod",
            owner_team=team or "platform",
            commit_sha=sha,
        )
        assert len(record.service_name) >= 1
        assert record.cost_amount > 0.0
        assert not math.isnan(record.cost_amount)
        assert not math.isinf(record.cost_amount)
    except ValidationError:
        pass

    llm_svc = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 30))
    llm_model = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 30))
    in_tokens = fdp.ConsumeIntInRange(-500, 500_000)
    out_tokens = fdp.ConsumeIntInRange(-500, 500_000)
    env_choices = ["dev", "staging", "prod", "canary", "test", ""]
    selected_env = env_choices[fdp.ConsumeIntInRange(0, len(env_choices) - 1)]

    try:
        req = LLMTelemetryRequest(
            service_name=llm_svc,
            model=llm_model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            environment=selected_env,  # type: ignore[arg-type]
        )
        assert len(req.service_name) >= 1
        assert len(req.model) >= 1
        assert req.input_tokens >= 0
        assert req.output_tokens >= 0
        assert req.input_tokens + req.output_tokens > 0
        assert req.environment in ("dev", "staging", "prod")
    except (ValidationError, ValueError):
        pass


def _fuzz_anomaly_detector(fdp: _DataProviderProtocol) -> None:
    """Fuzz AnomalyDetector.evaluate() for poisoning protection and stability."""
    detector = _get_fuzz_detector()
    detector.reset()

    project = "fuzz-tenant"
    environment = "prod"
    service_name = "fuzz-cloud-api"
    key = (project, environment, service_name)

    readings_count = fdp.ConsumeIntInRange(4, 10)

    for i in range(readings_count):
        if i < 3:
            cost = fdp.ConsumeFloatInRange(10.0, 50.0)
        else:
            if fdp.ConsumeBool():
                cost = fdp.ConsumeFloatInRange(15.0, 60.0)
            else:
                cost = fdp.ConsumeFloatInRange(200.0, 10_000.0)

        record = CostRecord(
            service_name=service_name,
            cost_amount=cost,
            currency="EUR",
            project=project,
            environment=environment,
            owner_team="platform-finops",
        )

        prev_len = len(detector.history[key])
        report = detector.evaluate(record)

        assert not math.isnan(
            report.deviation_percentage
        ), f"Deviation % is NaN for cost={cost}"
        assert not math.isinf(
            report.deviation_percentage
        ), f"Deviation % is Inf for cost={cost}"
        assert not math.isnan(
            report.historical_mean
        ), f"Historical mean is NaN for cost={cost}"
        assert report.current_cost == cost, "Current cost must match record"

        new_len = len(detector.history[key])
        if report.is_anomaly:
            assert new_len == prev_len, (
                f"Poisoning detected: Anomaly cost {cost} added to history. "
                f"Length before={prev_len}, after={new_len}"
            )
            assert cost not in list(
                detector.history[key]
            ), f"Poisoning detected: Anomaly cost {cost} present in history queue"
        else:
            expected_len = min(detector.MAX_HISTORY_WINDOW, prev_len + 1)
            assert (
                new_len == expected_len
            ), f"Expected history length {expected_len}, got {new_len}"

    detector.reset()


def TestOneInput(data: bytes) -> None:  # noqa: N802
    """libFuzzer entrypoint exercising pricing, schemas, and anomaly detector."""
    fdp = _get_data_provider(data)
    _fuzz_pricing_calculator(fdp)
    _fuzz_schema_validation(fdp)
    _fuzz_anomaly_detector(fdp)


def run_deterministic_self_test(iterations: int = 50) -> None:
    """Execute deterministic pseudo-entropy passes for regression testing and CI."""
    for i in range(iterations):
        seed_bytes = bytes([(i * 37 + j * 19 + 7) % 256 for j in range(512)])
        TestOneInput(seed_bytes)


def main() -> None:
    """Entry point for coverage-guided fuzzing or self-testing."""
    if "--self-test" in sys.argv:
        print("Running deterministic fuzzing self-test...")
        run_deterministic_self_test(iterations=50)
        print("Deterministic self-test passed successfully (50 iterations).")
        return

    if atheris is not None:
        atheris.Setup(sys.argv, TestOneInput)
        atheris.Fuzz()
    else:
        print(
            "Atheris is not installed in this environment. "
            "Executing deterministic self-test fallback..."
        )
        run_deterministic_self_test(iterations=50)
        print("Deterministic fallback self-test passed successfully (50 iterations).")


if __name__ == "__main__":
    main()
