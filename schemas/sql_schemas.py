from typing import Any, Literal

from pydantic import BaseModel, Field


class SQLValidationResult(BaseModel):
    """
    Standard result returned by the SQL validator.
    """

    is_valid: bool

    status: Literal[
        "approved",
        "rejected",
    ]

    normalized_sql: str | None = None
    statement_type: str | None = None

    referenced_tables: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class QueryExecutionResult(BaseModel):
    """
    Standard result returned by the query executor.
    """

    success: bool

    status: Literal[
        "completed",
        "validation_failed",
        "execution_failed",
    ]

    columns: list[str] = Field(
        default_factory=list
    )

    rows: list[dict[str, Any]] = Field(
        default_factory=list
    )

    returned_row_count: int = 0
    truncated: bool = False

    execution_time_ms: float | None = None
    sql: str | None = None

    validation: SQLValidationResult | None = None

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )