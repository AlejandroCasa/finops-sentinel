"""Pydantic data models for FinOps Sentinel."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CostRecord(BaseModel):
    """Represents a cloud service cost telemetry record."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
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
    project: str = Field(
        default="default",
        min_length=1,
        description="Project or tenant identifier for multi-tenant isolation.",
    )
    environment: str = Field(
        default="prod",
        description="Deployment environment (e.g. dev, staging, prod).",
    )
    owner_team: str = Field(
        default="platform",
        description="Team responsible for cloud resource cost attribution.",
    )
    commit_sha: str | None = Field(
        default=None,
        description="Optional Git commit SHA associated with the deployment.",
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
    project: str = Field(
        default="default",
        description="Project or tenant identifier.",
    )
    environment: str = Field(
        default="prod",
        description="Deployment environment.",
    )
    owner_team: str = Field(
        default="platform",
        description="Owner team attribution.",
    )
    commit_sha: str | None = Field(
        default=None,
        description="Git commit SHA associated with the cost reading.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the anomaly evaluation.",
    )


class ProjectGuardResponse(BaseModel):
    """Budget guard circuit breaker response for CI/CD gates and AI agents."""

    project: str = Field(..., description="Project identifier.")
    allowed: bool = Field(
        ...,
        description="True if execution is permitted, False if blocked by budget.",
    )
    reason: str = Field(..., description="Explanation of the guard decision.")
    total_cost: float = Field(
        ...,
        description="Cumulative recorded cost for the project.",
    )
    budget_limit: float = Field(
        ...,
        description="Hard spending limit configured for the project.",
    )
    anomaly_count: int = Field(
        ...,
        description="Number of active anomalies detected for the project.",
    )


class BatchTelemetryRequest(BaseModel):
    """Batch ingestion request payload containing multiple cost telemetry records."""

    records: list[CostRecord] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of cost telemetry records to evaluate (1 to 500 records).",
    )


class BatchTelemetryResponse(BaseModel):
    """Summary of batch telemetry evaluation and anomaly detection."""

    total_processed: int = Field(
        ...,
        description="Total number of records processed in the batch.",
    )
    anomalies_detected: int = Field(
        ...,
        description="Total number of anomalies detected across all batch records.",
    )
    reports: list[AnomalyReport] = Field(
        ...,
        description="Detailed anomaly evaluation report for each ingested record.",
    )


class LLMTelemetryRequest(BaseModel):
    """Telemetry payload for LLM token usage and automated cost estimation."""

    service_name: str = Field(
        ...,
        min_length=1,
        description="Name of the service generating token usage.",
    )
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier (e.g. gpt-4o, claude-3-5-sonnet).",
    )
    input_tokens: int = Field(
        ...,
        ge=0,
        description="Number of prompt/input tokens consumed.",
    )
    output_tokens: int = Field(
        ...,
        ge=0,
        description="Number of completion/output tokens generated.",
    )
    project: str = Field(
        default="default",
        min_length=1,
        description="Project or tenant identifier.",
    )
    environment: Literal["dev", "staging", "prod"] = Field(
        default="prod",
        description="Deployment environment (dev, staging, prod).",
    )
    owner_team: str = Field(
        default="platform",
        description="Team responsible for cost attribution.",
    )
    commit_sha: str | None = Field(
        default=None,
        description="Optional Git commit SHA associated with the deployment.",
    )

    @model_validator(mode="after")
    def validate_positive_tokens(self) -> "LLMTelemetryRequest":
        """Ensure that combined token count is strictly greater than zero."""
        if self.input_tokens + self.output_tokens <= 0:
            raise ValueError(
                "Combined input_tokens and output_tokens must be greater than zero."
            )
        return self


class LLMAnomalyReport(AnomalyReport):
    """Anomaly report for LLM telemetry including calculated USD cost."""

    calculated_cost_usd: float = Field(
        ...,
        description="Calculated cost in USD derived from token usage.",
    )


class FOCUSTelemetryRequest(BaseModel):
    """FOCUS 1.0 telemetry request with column aliases and cost validation."""

    model_config = ConfigDict(populate_by_name=True)

    billed_cost: float = Field(
        ...,
        alias="BilledCost",
        ge=0.0,
        description="FOCUS BilledCost amount.",
    )
    effective_cost: float = Field(
        ...,
        alias="EffectiveCost",
        ge=0.0,
        description="FOCUS EffectiveCost amount.",
    )
    service_name: str = Field(
        ...,
        alias="ServiceName",
        min_length=1,
        description="FOCUS ServiceName.",
    )
    region_id: str = Field(
        default="global",
        alias="RegionId",
        min_length=1,
        description="FOCUS RegionId.",
    )
    billing_currency: str = Field(
        default="USD",
        alias="BillingCurrency",
        min_length=3,
        max_length=3,
        description="ISO 4217 BillingCurrency.",
    )
    sub_account_id: str = Field(
        default="default",
        alias="SubAccountId",
        min_length=1,
        description="FOCUS SubAccountId mapped to project.",
    )
    environment: Literal["dev", "staging", "prod"] = Field(
        default="prod",
        description="Deployment environment.",
    )
    owner_team: str = Field(
        default="platform",
        description="Team attribution.",
    )
    commit_sha: str | None = Field(
        default=None,
        description="Optional Git commit SHA.",
    )

    @model_validator(mode="after")
    def validate_positive_focus_cost(self) -> "FOCUSTelemetryRequest":
        """Ensure either EffectiveCost or BilledCost is strictly greater than zero."""
        if not (self.effective_cost > 0 or self.billed_cost > 0):
            raise ValueError(
                "Either EffectiveCost or BilledCost must be strictly greater than zero."
            )
        return self


class FOCUSAnomalyReport(AnomalyReport):
    """Anomaly report for FOCUS 1.0 telemetry specification."""

    billed_cost: float = Field(..., description="FOCUS BilledCost evaluated.")
    effective_cost: float = Field(..., description="FOCUS EffectiveCost evaluated.")
    region_id: str = Field(..., description="Cloud region identifier.")
