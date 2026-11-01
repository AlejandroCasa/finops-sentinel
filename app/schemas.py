"""Pydantic data models for FinOps Sentinel."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class CostRecord(BaseModel):
    """Represents a cloud service cost telemetry record."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the cost reading.",
    )
    service_name: str = Field(
        ...,
        min_length=1,
        description="Name of the cloud service generating the cost.",
    )
    cost_amount: float = Field(
        ...,
        gt=0,
        description="Recorded cost amount (must be strictly greater than zero).",
    )
    currency: str = Field(
        default="EUR",
        description="ISO 4217 currency code.",
    )


class AnomalyReport(BaseModel):
    """Represents the anomaly detection evaluation result for a cost record."""

    is_anomaly: bool = Field(
        ...,
        description="Indicates whether the cost reading is considered anomalous.",
    )
    deviation_percentage: float = Field(
        ...,
        description="Percentage deviation from the historical mean.",
    )
    current_cost: float = Field(
        ...,
        description="Current evaluated cost amount.",
    )
    historical_mean: float = Field(
        ...,
        description="Calculated historical mean prior to the reading.",
    )
    service_name: str = Field(
        ...,
        description="Name of the evaluated cloud service.",
    )
