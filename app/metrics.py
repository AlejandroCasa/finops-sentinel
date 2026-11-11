"""Prometheus metrics registry and text exposition formatter for FinOps Sentinel."""

from collections import Counter
import threading


class MetricsRegistry:
    """Thread-safe in-memory metrics registry for Prometheus exposition."""

    def __init__(self) -> None:
        """Initialize empty metric stores and thread synchronization lock."""
        self._lock = threading.Lock()
        self._telemetry_ingested: Counter[tuple[str, str]] = Counter()
        self._anomalies_detected: Counter[str] = Counter()
        self._service_cost_gauge: dict[tuple[str, str], float] = {}

    def record_telemetry(self, service: str, currency: str, cost: float) -> None:
        """Record an ingested telemetry event and update the latest cost gauge.

        Args:
            service: Cloud service identifier (e.g., 'compute-cluster').
            currency: ISO 4217 currency code (e.g., 'EUR').
            cost: Evaluated cost amount.
        """
        with self._lock:
            key = (service, currency)
            self._telemetry_ingested[key] += 1
            self._service_cost_gauge[key] = float(cost)

    def record_anomaly(self, service: str) -> None:
        """Increment the anomaly counter for the given cloud service.

        Args:
            service: Cloud service identifier triggering the anomaly.
        """
        with self._lock:
            self._anomalies_detected[service] += 1

    def generate_prometheus_exposition(self) -> str:
        """Serialize registered metrics to Prometheus text exposition format (0.0.4).

        Returns:
            Newline-terminated Prometheus text exposition string.
        """
        with self._lock:
            lines: list[str] = []

            # Metric 1: finops_telemetry_ingested_total (Counter)
            lines.append(
                "# HELP finops_telemetry_ingested_total "
                "Total cost telemetry records ingested."
            )
            lines.append("# TYPE finops_telemetry_ingested_total counter")
            if self._telemetry_ingested:
                for (service, currency), count in sorted(
                    self._telemetry_ingested.items()
                ):
                    label_part = (
                        f'currency="{currency}",service="{service}"'
                    )
                    val = float(count)
                    lines.append(
                        f"finops_telemetry_ingested_total{{{label_part}}} {val}"
                    )
            else:
                lines.append("finops_telemetry_ingested_total 0.0")

            # Metric 2: finops_anomalies_detected_total (Counter)
            lines.append(
                "# HELP finops_anomalies_detected_total Total cost anomalies detected."
            )
            lines.append("# TYPE finops_anomalies_detected_total counter")
            if self._anomalies_detected:
                for service, count in sorted(self._anomalies_detected.items()):
                    lines.append(
                        f'finops_anomalies_detected_total{{service="{service}"}} '
                        f"{float(count)}"
                    )
            else:
                lines.append("finops_anomalies_detected_total 0.0")

            # Metric 3: finops_service_cost_amount_gauge (Gauge)
            lines.append(
                "# HELP finops_service_cost_amount_gauge "
                "Current recorded cost amount per service."
            )
            lines.append("# TYPE finops_service_cost_amount_gauge gauge")
            if self._service_cost_gauge:
                for (service, currency), amount in sorted(
                    self._service_cost_gauge.items()
                ):
                    label_part = (
                        f'currency="{currency}",service="{service}"'
                    )
                    lines.append(
                        f"finops_service_cost_amount_gauge{{{label_part}}} "
                        f"{float(amount)}"
                    )
            else:
                lines.append("finops_service_cost_amount_gauge 0.0")

            lines.append("")
            return "\n".join(lines)

    def reset(self) -> None:
        """Clear all metric counters and gauges to ensure test isolation."""
        with self._lock:
            self._telemetry_ingested.clear()
            self._anomalies_detected.clear()
            self._service_cost_gauge.clear()


metrics_registry = MetricsRegistry()
