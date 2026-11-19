from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryOperation(str, Enum):
    AGGREGATE = "aggregate"
    RANK = "rank"
    COMPARE = "compare"
    TREND = "trend"


class QueryFilter(BaseModel):
    field: str
    operator: str
    value: Any


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

    sort_metric: str | None = None
    sort_direction: str | None = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )