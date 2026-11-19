from __future__ import annotations

from typing import Any

import pandas as pd

from schemas.planning_schemas import (
    AnalyticalTask,
)
from schemas.result_validation_schemas import (
    ColumnProfile,
    ResultValidationIssue,
    ResultValidationResult,
    ValidationSeverity,
)
from schemas.sql_schemas import (
    QueryExecutionResult,
)


def _infer_column_type(
    series: pd.Series,
) -> str:
    """
    Infer a simple business-friendly data type.
    """

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    if pd.api.types.is_datetime64_any_dtype(
        series
    ):
        return "datetime"

    return "text"


def _safe_sample_values(
    series: pd.Series,
    sample_size: int = 3,
) -> list:
    """
    Return a small JSON-friendly sample of non-null values.
    """

    values = (
        series
        .dropna()
        .head(sample_size)
        .tolist()
    )

    serialized_values: list[Any] = []

    for value in values:
        if hasattr(value, "isoformat"):
            serialized_values.append(
                value.isoformat()
            )
        elif isinstance(
            value,
            (str, int, float, bool),
        ):
            serialized_values.append(value)
        else:
            serialized_values.append(
                str(value)
            )

    return serialized_values


def _profile_dataframe(
    dataframe: pd.DataFrame,
) -> list[ColumnProfile]:
    """
    Build lightweight quality profiles for each column.
    """

    profiles: list[ColumnProfile] = []

    row_count = len(dataframe)

    for column_name in dataframe.columns:
        series = dataframe[column_name]

        null_count = int(
            series.isna().sum()
        )

        non_null_count = int(
            series.notna().sum()
        )

        unique_count = int(
            series.nunique(
                dropna=True
            )
        )

        null_percentage = (
            round(
                (
                    null_count
                    / row_count
                    * 100
                ),
                2,
            )
            if row_count > 0
            else 0.0
        )

        profiles.append(
            ColumnProfile(
                column_name=str(column_name),
                inferred_type=(
                    _infer_column_type(series)
                ),
                non_null_count=non_null_count,
                null_count=null_count,
                unique_count=unique_count,
                null_percentage=(
                    null_percentage
                ),
                sample_values=(
                    _safe_sample_values(
                        series
                    )
                ),
            )
        )

    return profiles


def validate_query_result(
    task: AnalyticalTask,
    execution: QueryExecutionResult,
) -> ResultValidationResult:
    """
    Validate an executed query against its analytical task.

    The result is invalid when:
    - execution failed,
    - expected columns are missing,
    - the result is empty,
    - an expected metric column contains only null values.

    Extra columns and duplicate rows produce warnings.
    """

    issues: list[
        ResultValidationIssue
    ] = []

    if not execution.success:
        issues.append(
            ResultValidationIssue(
                code="EXECUTION_FAILED",
                message=(
                    "The query result cannot be "
                    "validated because execution failed."
                ),
                severity=ValidationSeverity.ERROR,
                details={
                    "execution_errors": (
                        execution.errors
                    )
                },
            )
        )

        return ResultValidationResult(
            is_valid=False,
            task_id=task.task_id,
            expected_columns=(
                task.expected_columns
            ),
            actual_columns=(
                execution.columns
            ),
            issues=issues,
        )

    dataframe = pd.DataFrame(
        execution.rows,
        columns=execution.columns,
    )

    expected_columns = list(
        task.expected_columns
    )

    actual_columns = [
        str(column)
        for column in dataframe.columns
    ]

    expected_column_set = set(
        expected_columns
    )

    actual_column_set = set(
        actual_columns
    )

    missing_columns = sorted(
        expected_column_set
        - actual_column_set
    )

    unexpected_columns = sorted(
        actual_column_set
        - expected_column_set
    )

    for column_name in missing_columns:
        issues.append(
            ResultValidationIssue(
                code=(
                    "MISSING_EXPECTED_COLUMN"
                ),
                message=(
                    f"Expected column "
                    f"{column_name} was not returned."
                ),
                severity=ValidationSeverity.ERROR,
                field=column_name,
            )
        )

    if unexpected_columns:
        issues.append(
            ResultValidationIssue(
                code="UNEXPECTED_COLUMNS",
                message=(
                    "The query returned additional "
                    "columns not listed in the task."
                ),
                severity=ValidationSeverity.WARNING,
                details={
                    "columns": unexpected_columns
                },
            )
        )

    row_count = len(dataframe)
    empty_result = dataframe.empty

    if empty_result:
        issues.append(
            ResultValidationIssue(
                code="EMPTY_RESULT",
                message=(
                    "The query executed successfully "
                    "but returned no rows."
                ),
                severity=ValidationSeverity.ERROR,
            )
        )

    duplicate_row_count = int(
        dataframe.duplicated().sum()
    )

    if duplicate_row_count > 0:
        issues.append(
            ResultValidationIssue(
                code="DUPLICATE_ROWS",
                message=(
                    f"The result contains "
                    f"{duplicate_row_count} duplicate "
                    "row or rows."
                ),
                severity=ValidationSeverity.WARNING,
                details={
                    "duplicate_row_count": (
                        duplicate_row_count
                    )
                },
            )
        )

    for metric_name in task.metrics:
        matching_columns = [
            column
            for column in actual_columns
            if (
                metric_name.lower().replace(
                    "_",
                    "",
                )
                in column.lower().replace(
                    "_",
                    "",
                )
            )
        ]

        for column_name in matching_columns:
            if (
                not dataframe.empty
                and dataframe[
                    column_name
                ].isna().all()
            ):
                issues.append(
                    ResultValidationIssue(
                        code=(
                            "METRIC_ALL_NULL"
                        ),
                        message=(
                            f"Metric column "
                            f"{column_name} contains "
                            "only null values."
                        ),
                        severity=(
                            ValidationSeverity.ERROR
                        ),
                        field=column_name,
                    )
                )

    if execution.truncated:
        issues.append(
            ResultValidationIssue(
                code="RESULT_TRUNCATED",
                message=(
                    "The returned result was truncated "
                    "by the executor row limit."
                ),
                severity=ValidationSeverity.WARNING,
            )
        )

    error_exists = any(
        issue.severity
        == ValidationSeverity.ERROR
        for issue in issues
    )

    validated_rows = (
        dataframe
        .where(
            pd.notna(dataframe),
            None,
        )
        .to_dict(
            orient="records"
        )
    )

    return ResultValidationResult(
        is_valid=not error_exists,
        task_id=task.task_id,
        expected_columns=expected_columns,
        actual_columns=actual_columns,
        missing_columns=missing_columns,
        unexpected_columns=(
            unexpected_columns
        ),
        row_count=row_count,
        empty_result=empty_result,
        duplicate_row_count=(
            duplicate_row_count
        ),
        column_profiles=(
            _profile_dataframe(
                dataframe
            )
        ),
        issues=issues,
        validated_rows=validated_rows,
    )