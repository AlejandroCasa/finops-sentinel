"""Push webhook notifier with anti-spam cooldown deduplication."""

import json
import threading
import time
import urllib.request
from typing import Any

from app.config import settings
from app.schemas import AnomalyReport


def _is_valid_url(url: str) -> bool:
    """Check if the provided URL has a supported HTTP or HTTPS scheme."""
    return bool(url and (url.startswith("http://") or url.startswith("https://")))


class WebhookNotifier:
    """Dispatches anomaly notifications to webhooks with deduplication cooldown."""

    def __init__(self) -> None:
        """Initialize in-memory cooldown cache and thread lock."""
        self._lock = threading.Lock()
        self._last_alert_time: dict[tuple[str, str, str], float] = {}

    def _is_rate_limited(self, key: tuple[str, str, str], cooldown: int) -> bool:
        """Check and update anti-spam cooldown timestamp."""
        now = time.monotonic()
        with self._lock:
            last = self._last_alert_time.get(key)
            if last is not None and (now - last) < cooldown:
                return True
            self._last_alert_time[key] = now
            return False

    def _post_payload(self, url: str, report: AnomalyReport) -> bool:
        """Serialize report and POST JSON payload to the remote webhook."""
        payload: dict[str, Any] = {
            "text": (
                f"FinOps Anomaly: {report.service_name} "
                f"({report.project}/{report.environment}) spiked by "
                f"+{report.deviation_percentage:.1f}% "
                f"({report.current_cost:.4f} vs mean {report.historical_mean:.4f})"
            ),
            "service_name": report.service_name,
            "project": report.project,
            "environment": report.environment,
            "current_cost": report.current_cost,
            "historical_mean": report.historical_mean,
            "deviation_percentage": report.deviation_percentage,
            "owner_team": report.owner_team,
            "commit_sha": report.commit_sha,
            "timestamp": report.timestamp.isoformat(),
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "FinOps-Sentinel/0.2.0",
                },
                method="POST",
            )
            # Safe URL open: protocol strictly validated as http:// or https://
            with urllib.request.urlopen(req, timeout=3.0) as resp:  # nosec B310
                return bool(resp.status in (200, 201, 202, 204))
        except Exception:
            # Gracefully catch network errors or timeouts so ingestion never fails
            return False

    def send_alert(
        self,
        report: AnomalyReport,
        webhook_url: str | None = None,
        cooldown_seconds: int | None = None,
    ) -> bool:
        """Dispatch a JSON webhook notification if cooldown window has expired.

        Args:
            report: Evaluated anomaly report to dispatch.
            webhook_url: Optional URL override; defaults to settings.webhook_url.
            cooldown_seconds: Optional cooldown override; defaults to settings.

        Returns:
            True if notification was successfully sent, False otherwise.
        """
        url = webhook_url if webhook_url is not None else settings.webhook_url
        if not _is_valid_url(url):
            return False

        cooldown = (
            cooldown_seconds
            if cooldown_seconds is not None
            else settings.webhook_cooldown_seconds
        )
        key = (report.project, report.environment, report.service_name)
        if self._is_rate_limited(key, cooldown):
            return False

        return self._post_payload(url, report)

    def reset(self) -> None:
        """Clear the cooldown history to guarantee test isolation."""
        with self._lock:
            self._last_alert_time.clear()


webhook_notifier = WebhookNotifier()
