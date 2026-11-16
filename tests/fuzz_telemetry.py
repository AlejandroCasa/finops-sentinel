"""Coverage-guided Atheris fuzzing harness for FinOps Sentinel telemetry engine."""

from fuzz.fuzz_telemetry import TestOneInput, main, run_deterministic_self_test

__all__ = ["TestOneInput", "main", "run_deterministic_self_test"]

if __name__ == "__main__":
    main()
