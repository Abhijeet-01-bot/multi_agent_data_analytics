from schemas.analytics_schemas import (
    AnalyticsOperation,
    AnalyticsResult,
)
from schemas.result_validation_schemas import (
    ResultValidationResult,
)
from schemas.sql_generation_schemas import (
    GeneratedSQLQuery,
    SQLTaskResult,
)
from schemas.sql_schemas import (
    QueryExecutionResult,
    SQLValidationResult,
)
from services.evidence_service import (
    build_evidence_bundle,
    create_calculation_evidence,
    create_query_evidence,
)


def build_sql_task_result() -> SQLTaskResult:
    query = GeneratedSQLQuery(
        task_id="T1",
        sql="""
            SELECT
                CategoryName,
                NetRevenue
            FROM CategoryRevenue
        """,
        parameters={},
        referenced_tables=[
            "Categories"
        ],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
        explanation="Test query.",
    )

    sql_validation = SQLValidationResult(
        is_valid=True,
        status="approved",
        statement_type="SELECT",
        referenced_tables=[
            "Categories"
        ],
    )

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
    )

    return SQLTaskResult(
        success=True,
        task_id="T1",
        attempts=1,
        query=query,
        validation=sql_validation,
        execution=execution,
    )


def build_result_validation() -> (
    ResultValidationResult
):
    return ResultValidationResult(
        is_valid=True,
        task_id="T1",
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
        actual_columns=[
            "CategoryName",
            "NetRevenue",
        ],
        row_count=1,
        validated_rows=[
            {
                "CategoryName": "Beverages",
                "NetRevenue": 1000.0,
            }
        ],
    )


def test_create_query_evidence() -> None:
    evidence = create_query_evidence(
        sql_task_result=(
            build_sql_task_result()
        ),
        validation_result=(
            build_result_validation()
        ),
    )

    assert evidence.task_id == "T1"
    assert evidence.validated is True
    assert evidence.source_columns == [
        "CategoryName",
        "NetRevenue",
    ]
    assert len(evidence.source_rows) == 1


def test_create_calculation_evidence() -> None:
    analytics_result = AnalyticsResult(
        success=True,
        operation=(
            AnalyticsOperation.RANKING
        ),
        summary="Ranked one category.",
        records=[
            {
                "rank": 1,
                "label": "Beverages",
                "value": 1000.0,
            }
        ],
    )

    evidence = create_calculation_evidence(
        task_id="T1",
        calculation_name=(
            "Category revenue ranking"
        ),
        description=(
            "Ranks categories by net revenue."
        ),
        inputs={
            "label_column": "CategoryName",
            "value_column": "NetRevenue",
        },
        analytics_result=analytics_result,
    )

    assert evidence.validated is True
    assert (
        evidence.calculation_name
        == "Category revenue ranking"
    )
    assert evidence.calculation_output[
        "success"
    ] is True


def test_build_evidence_bundle() -> None:
    query_evidence = create_query_evidence(
        sql_task_result=(
            build_sql_task_result()
        ),
        validation_result=(
            build_result_validation()
        ),
    )

    bundle = build_evidence_bundle(
        request_id="REQ-001",
        records=[query_evidence],
    )

    assert bundle.request_id == "REQ-001"
    assert bundle.record_count == 1
    assert bundle.validated_record_count == 1


def test_unsuccessful_sql_task_is_rejected() -> None:
    unsuccessful_result = SQLTaskResult(
        success=False,
        task_id="T1",
        attempts=1,
        errors=["Query failed."],
    )

    try:
        create_query_evidence(
            sql_task_result=(
                unsuccessful_result
            ),
            validation_result=(
                build_result_validation()
            ),
        )

        assert False, (
            "Unsuccessful SQL result should fail."
        )

    except ValueError as error:
        assert "unsuccessful" in str(error)