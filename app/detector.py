"""Anomaly detection engine with multi-tenant baselines and SQLite persistence."""

import sqlite3
from collections import defaultdict, deque

from app.config import settings
from app.schemas import AnomalyReport, CostRecord, ProjectGuardResponse


class AnomalyDetector:
    """Detects cost anomalies per service with multi-tenant isolation and SQLite."""

    CALIBRATION_MIN_READINGS: int = 3
    DEVIATION_THRESHOLD_PERCENT: float = 25.0
    MAX_HISTORY_WINDOW: int = 30

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize in-memory storage and SQLite persistence layer."""
        self.db_path = db_path or settings.db_path
        self.history: defaultdict[tuple[str, str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=self.MAX_HISTORY_WINDOW)
        )
        self.alerts: list[AnomalyReport] = []
        self._init_db()

    def _init_db(self) -> None:
        """Create database tables if they do not exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cost_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    cost_amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    owner_team TEXT NOT NULL,
                    commit_sha TEXT,
                    timestamp TEXT NOT NULL
                )
                """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cost_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    is_anomaly INTEGER NOT NULL,
                    deviation_percentage REAL NOT NULL,
                    current_cost REAL NOT NULL,
                    historical_mean REAL NOT NULL,
                    owner_team TEXT NOT NULL,
                    commit_sha TEXT,
                    timestamp TEXT NOT NULL
                )
                """)
            conn.commit()

    def _persist_reading(self, record: CostRecord) -> None:
        """Persist ingested cost reading into SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cost_readings (
                    project, environment, service_name, cost_amount,
                    currency, owner_team, commit_sha, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.project,
                    record.environment,
                    record.service_name,
                    record.cost_amount,
                    record.currency,
                    record.owner_team,
                    record.commit_sha,
                    record.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def _persist_alert(self, report: AnomalyReport) -> None:
        """Persist detected anomaly report into SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cost_alerts (
                    project, environment, service_name, is_anomaly,
                    deviation_percentage, current_cost, historical_mean,
                    owner_team, commit_sha, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.project,
                    report.environment,
                    report.service_name,
                    1 if report.is_anomaly else 0,
                    report.deviation_percentage,
                    report.current_cost,
                    report.historical_mean,
                    report.owner_team,
                    report.commit_sha,
                    report.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def evaluate(self, record: CostRecord) -> AnomalyReport:
        """Evaluate a cost record against its project-environment-service baseline."""
        self._persist_reading(record)
        key = (record.project, record.environment, record.service_name)
        service_readings = self.history[key]

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
                project=record.project,
                environment=record.environment,
                owner_team=record.owner_team,
                commit_sha=record.commit_sha,
                timestamp=record.timestamp,
            )

        historical_mean = sum(service_readings) / len(service_readings)
        deviation_percentage = (
            (record.cost_amount - historical_mean) / historical_mean
        ) * 100.0
        is_anomaly = deviation_percentage > self.DEVIATION_THRESHOLD_PERCENT

        # Baseline poisoning protection: anomalous readings are excluded
        if not is_anomaly:
            service_readings.append(record.cost_amount)

        report = AnomalyReport(
            is_anomaly=is_anomaly,
            deviation_percentage=deviation_percentage,
            current_cost=record.cost_amount,
            historical_mean=historical_mean,
            service_name=record.service_name,
            project=record.project,
            environment=record.environment,
            owner_team=record.owner_team,
            commit_sha=record.commit_sha,
            timestamp=record.timestamp,
        )

        if is_anomaly:
            self.alerts.append(report)
            self._persist_alert(report)

        return report

    def get_guard_status(self, project: str) -> ProjectGuardResponse:
        """Evaluate circuit breaker status based on project spend and anomalies."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(cost_amount), 0.0) "
                "FROM cost_readings WHERE project = ?",
                (project,),
            )
            cost_row = cursor.fetchone()
            total_cost: float = float(cost_row[0]) if cost_row else 0.0

            cursor.execute(
                "SELECT COUNT(*) FROM cost_alerts WHERE project = ? AND is_anomaly = 1",
                (project,),
            )
            anomaly_row = cursor.fetchone()
            anomaly_count: int = int(anomaly_row[0]) if anomaly_row else 0

        budget_limit = settings.budget_default_limit
        max_anomalies = settings.max_anomalies_before_block

        if total_cost > budget_limit:
            return ProjectGuardResponse(
                project=project,
                allowed=False,
                reason=(
                    f"Project total spend {total_cost:.2f} "
                    f"exceeds hard budget {budget_limit:.2f}"
                ),
                total_cost=total_cost,
                budget_limit=budget_limit,
                anomaly_count=anomaly_count,
            )

        if anomaly_count >= max_anomalies:
            return ProjectGuardResponse(
                project=project,
                allowed=False,
                reason=(
                    f"Project triggered {anomaly_count} anomalies "
                    f"(threshold: {max_anomalies})"
                ),
                total_cost=total_cost,
                budget_limit=budget_limit,
                anomaly_count=anomaly_count,
            )

        return ProjectGuardResponse(
            project=project,
            allowed=True,
            reason=(
                "Project spend and anomaly counts within normal "
                "operational parameters"
            ),
            total_cost=total_cost,
            budget_limit=budget_limit,
            anomaly_count=anomaly_count,
        )

    def get_alerts(self, project: str | None = None) -> list[AnomalyReport]:
        """Return all persisted anomaly reports, optionally filtered by project."""
        if project:
            return [a for a in self.alerts if a.project == project]
        return list(self.alerts)

    def reset(self) -> None:
        """Clear memory cache and SQLite tables for test isolation."""
        self.history.clear()
        self.alerts.clear()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cost_readings")
            cursor.execute("DELETE FROM cost_alerts")
            conn.commit()
