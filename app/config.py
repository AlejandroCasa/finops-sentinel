"""Configuration settings for FinOps Sentinel validated via pydantic-settings."""

import os
import tempfile
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_path() -> str:
    """Return a writable temporary database path for read-only containers."""
    return os.path.join(tempfile.gettempdir(), "finops_sentinel.db")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="FINOPS_", extra="ignore")

    api_key: str | None = None
    db_path: str = Field(default_factory=_default_db_path)
    budget_default_limit: float = 1000.0
    max_anomalies_before_block: int = 3
    webhook_url: str = ""
    webhook_cooldown_seconds: int = 300
    detection_strategy: Literal["percentage", "zscore", "ewma"] = "percentage"
    deviation_threshold_percent: float = 25.0
    zscore_threshold: float = 2.5
    ewma_alpha: float = 0.3


settings = Settings()
