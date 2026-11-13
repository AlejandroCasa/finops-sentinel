"""In-memory anomaly detection engine for cloud cost telemetry."""

from collections import defaultdict, deque

from app.schemas import AnomalyReport, CostRecord


class AnomalyDetector:
    """Detects cost anomalies per service using a rolling historical baseline."""

    CALIBRATION_MIN_READINGS: int = 3
    DEVIATION_THRESHOLD_PERCENT: float = 25.0
    MAX_HISTORY_WINDOW: int = 30

    def __init__(self) -> None:
        """Initialize in-memory storage for service cost history and detected alerts."""
        self.history: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.MAX_HISTORY_WINDOW)
        )
        self.alerts: list[AnomalyReport] = []

    def evaluate(self, record: CostRecord) -> AnomalyReport:
        """Evaluate a new cost record against the service's historical baseline.

        Calibration rule:
            If the service has fewer than 3 prior readings, store the reading and
            return ``is_anomaly = False``.
        Deviation rule:
            With 3 or more prior readings, compute the historical mean. If the
            current cost exceeds the historical mean by more than 25%, mark
            ``is_anomaly = True`` and persist the report in the internal alerts list.
        Baseline poisoning protection:
            Anomalous readings (``is_anomaly = True``) are never appended to the
            historical baseline, ensuring rolling mean stability against cost spikes.
        """
        service_readings = self.history[record.service_name]

        if len(service_readings) < self.CALIBRATION_MIN_READINGS:
            historical_mean = (
                sum(service_readings) / len(service_readings)
                if service_readings
                else 0.0
            )
            service_readings.append(record.cost_amount)
            return AnomalyReport(
                is_anomaly=False,
                deviation_percentage=0.0,
                current_cost=record.cost_amount,
                historical_mean=historical_mean,
                service_name=record.service_name,
            )

        historical_mean = sum(service_readings) / len(service_readings)
        deviation_percentage = (
            (record.cost_amount - historical_mean) / historical_mean
        ) * 100.0
        is_anomaly = deviation_percentage > self.DEVIATION_THRESHOLD_PERCENT

        # Baseline poisoning protection: only normal readings are appended
        if not is_anomaly:
            service_readings.append(record.cost_amount)

        report = AnomalyReport(
            is_anomaly=is_anomaly,
            deviation_percentage=deviation_percentage,
            current_cost=record.cost_amount,
            historical_mean=historical_mean,
            service_name=record.service_name,
        )

        if is_anomaly:
            self.alerts.append(report)

        return report

    def get_alerts(self) -> list[AnomalyReport]:
        """Return all anomaly reports recorded so far."""
        return list(self.alerts)
