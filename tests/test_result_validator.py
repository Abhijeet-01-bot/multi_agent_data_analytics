from schemas.planning_schemas import (
    AnalyticalTask,
    TaskType,
)
from schemas.sql_schemas import (
    QueryExecutionResult,
)
from tools.result_validator import (
    validate_query_result,
)


def build_task() -> AnalyticalTask:
    return AnalyticalTask(
        task_id="T1",
        description=(
            "Calculate net revenue by category."
        ),
        task_type=TaskType.DATA_RETRIEVAL,
        metrics=["net_revenue"],
        dimensions=["category"],
        required_tables=[
            "Order Details",
            "Products",
            "Categories",
        ],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
    )


def test_valid_query_result() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
        ],
        rows=[
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            },
            {
                "CategoryName": "Confections",
                "NetRevenue": 800.0,
            },
        ],
        returned_row_count=2,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is True
    assert result.row_count == 2
    assert result.missing_columns == []
    assert result.empty_result is False

    profile_names = {
        profile.column_name
        for profile in result.column_profiles
    }

    assert "CategoryName" in profile_names
    assert "NetRevenue" in profile_names


def test_missing_column_is_invalid() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=["NetRevenue"],
        rows=[
            {
                "NetRevenue": 1000.0,
            }
        ],
        returned_row_count=1,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is False

    assert "CategoryName" in (
        result.missing_columns
    )

    assert any(
        issue.code
        == "MISSING_EXPECTED_COLUMN"
        for issue in result.issues
    )


def test_empty_result_is_invalid() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
        ],
        rows=[],
        returned_row_count=0,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is False
    assert result.empty_result is True

    assert any(
        issue.code == "EMPTY_RESULT"
        for issue in result.issues
    )


def test_failed_execution_is_invalid() -> None:
    execution = QueryExecutionResult(
        success=False,
        status="execution_failed",
        errors=[
            "Database execution failed."
        ],
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is False

    assert any(
        issue.code == "EXECUTION_FAILED"
        for issue in result.issues
    )


def test_duplicate_rows_create_warning() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
        ],
        rows=[
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            },
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            },
        ],
        returned_row_count=2,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is True
    assert result.duplicate_row_count == 1

    assert any(
        issue.code == "DUPLICATE_ROWS"
        for issue in result.issues
    )


def test_unexpected_column_creates_warning() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
            "ExtraColumn",
        ],
        rows=[
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
                "ExtraColumn": "value",
            }
        ],
        returned_row_count=1,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is True

    assert result.unexpected_columns == [
        "ExtraColumn"
    ]


def test_truncated_result_creates_warning() -> None:
    execution = QueryExecutionResult(
        success=True,
        status="completed",
        columns=[
            "CategoryName",
            "NetRevenue",
        ],
        rows=[
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            }
        ],
        returned_row_count=1,
        truncated=True,
    )

    result = validate_query_result(
        task=build_task(),
        execution=execution,
    )

    assert result.is_valid is True

    assert any(
        issue.code == "RESULT_TRUNCATED"
        for issue in result.issues
    )