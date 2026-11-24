from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QueryOperation(str, Enum):
    AGGREGATE = "aggregate"
    RANK = "rank"
    COMPARE = "compare"
    TREND = "trend"


class QuerySortDirection(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class QueryFilter(BaseModel):
    field: str
    operator: str
    value: Any

    @field_validator("operator")
    @classmethod
    def validate_operator(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        supported = {
            "equals",
            "not_equals",
            "in",
            "between",
            "greater_than",
            "less_than",
            "greater_than_or_equal",
            "less_than_or_equal",
        }

        if normalized not in supported:
            raise ValueError(
                "Unsupported filter operator: "
                f"{value}"
            )

        return normalized


class QuerySpec(BaseModel):
    metric: str

    dimensions: list[str] = Field(
        default_factory=list
    )

    filters: list[QueryFilter] = Field(
        default_factory=list
    )

    operations: list[QueryOperation] = Field(
        default_factory=list
    )

    sort_direction: (
        QuerySortDirection | None
    ) = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )