from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FilterOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"


class AnalysisType(str, Enum):
    AGGREGATION = "aggregation"
    RANKING = "ranking"
    COMPARISON = "comparison"
    TREND = "trend"
    CONTRIBUTION = "contribution"
    ROOT_CAUSE = "root_cause"
    ANOMALY = "anomaly"
    DISTRIBUTION = "distribution"
    DETAIL_LOOKUP = "detail_lookup"


class SortDirection(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class IntentFilter(BaseModel):
    field: str = Field(
        description=(
            "Canonical filter field, such as "
            "customer_country, ship_country, category, "
            "product, customer, order_date, or discount."
        )
    )

    operator: FilterOperator = Field(
        default=FilterOperator.EQUALS,
        description="Comparison operator for the filter.",
    )

    value: Any = Field(
        description="Filter value supplied by the user."
    )


class TimeRange(BaseModel):
    start_date: str | None = Field(
        default=None,
        description="ISO date in YYYY-MM-DD format.",
    )

    end_date: str | None = Field(
        default=None,
        description="ISO date in YYYY-MM-DD format.",
    )

    named_period: str | None = Field(
        default=None,
        description=(
            "User-provided period such as Q1, Q2, "
            "last month, or latest quarter."
        ),
    )

    comparison_period: str | None = Field(
        default=None,
        description=(
            "Period used as a comparison baseline."
        ),
    )


class IntentResult(BaseModel):
    business_objective: str = Field(
        description=(
            "Concise description of what the business "
            "user wants to understand."
        )
    )

    metrics: list[str] = Field(
        default_factory=list,
        description=(
            "Canonical metric names from the approved "
            "semantic metric catalog."
        ),
    )

    dimensions: list[str] = Field(
        default_factory=list,
        description=(
            "Business dimensions used to group or break "
            "down the metrics."
        ),
    )

    filters: list[IntentFilter] = Field(
        default_factory=list
    )

    time_range: TimeRange | None = None

    analysis_types: list[AnalysisType] = Field(
        default_factory=list
    )

    sort_direction: SortDirection | None = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    ambiguity_reasons: list[str] = Field(
        default_factory=list
    )

    clarification_required: bool = False

    clarification_question: str | None = None

    unsupported_request: bool = False

    unsupported_reason: str | None = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_clarification(self) -> "IntentResult":
        if (
            self.clarification_required
            and not self.clarification_question
        ):
            raise ValueError(
                "clarification_question is required when "
                "clarification_required is true."
            )

        if (
            self.unsupported_request
            and not self.unsupported_reason
        ):
            raise ValueError(
                "unsupported_reason is required when "
                "unsupported_request is true."
            )

        return self