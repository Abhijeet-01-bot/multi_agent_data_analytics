from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ResultValidationIssue(BaseModel):
    """
    One issue detected while validating a query result.
    """

    code: str

    message: str

    severity: ValidationSeverity

    field: str | None = None

    details: dict[str, Any] = Field(
        default_factory=dict
    )


class ColumnProfile(BaseModel):
    """
    Basic quality profile for one returned column.
    """

    column_name: str

    inferred_type: str

    non_null_count: int = 0
    null_count: int = 0
    unique_count: int = 0

    null_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    sample_values: list[Any] = Field(
        default_factory=list
    )


class ResultValidationResult(BaseModel):
    """
    Complete validation result for one executed query.
    """

    is_valid: bool

    task_id: str

    expected_columns: list[str] = Field(
        default_factory=list
    )

    actual_columns: list[str] = Field(
        default_factory=list
    )

    missing_columns: list[str] = Field(
        default_factory=list
    )

    unexpected_columns: list[str] = Field(
        default_factory=list
    )

    row_count: int = 0

    empty_result: bool = False

    duplicate_row_count: int = 0

    column_profiles: list[ColumnProfile] = Field(
        default_factory=list
    )

    issues: list[ResultValidationIssue] = Field(
        default_factory=list
    )

    validated_rows: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )