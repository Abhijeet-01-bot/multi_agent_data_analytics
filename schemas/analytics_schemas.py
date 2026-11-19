from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsOperation(str, Enum):
    SUMMARY = "summary"
    RANKING = "ranking"
    PERIOD_COMPARISON = "period_comparison"
    CONTRIBUTION = "contribution"
    GROWTH_RATE = "growth_rate"
    ANOMALY_DETECTION = "anomaly_detection"
    TREND = "trend"


class SummaryStatistics(BaseModel):
    column: str

    count: int
    null_count: int

    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    total: float | None = None


class RankingRecord(BaseModel):
    rank: int
    label: str
    value: float
    percentage_of_total: float | None = None


class GrowthResult(BaseModel):
    previous_value: float
    current_value: float

    absolute_change: float

    percentage_change: float | None = None

    direction: str

    warning: str | None = None


class ContributionRecord(BaseModel):
    label: str

    value: float

    contribution_percentage: float | None = None

    rank: int | None = None


class AnomalyRecord(BaseModel):
    index: int

    label: str | None = None

    value: float

    score: float

    method: str

    is_anomaly: bool


class AnalyticsResult(BaseModel):
    success: bool

    operation: AnalyticsOperation

    summary: str

    records: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )