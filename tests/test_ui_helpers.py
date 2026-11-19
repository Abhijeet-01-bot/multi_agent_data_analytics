from ui.renderers import (
    get_generated_sql,
    get_query_rows,
    get_sql_parameters,
    get_status_label,
)


def build_workflow_result() -> dict:
    return {
        "status": "completed",
        "sql_task_result": {
            "query": {
                "sql": (
                    "SELECT COUNT(*) "
                    "AS OrderCount FROM Orders"
                ),
                "parameters": {},
            },
            "execution": {
                "success": True,
                "columns": [
                    "OrderCount"
                ],
                "rows": [
                    {
                        "OrderCount": 830
                    }
                ],
            },
        },
    }


def test_get_status_label() -> None:
    assert (
        get_status_label("completed")
        == "Analysis completed"
    )

    assert (
        get_status_label(
            "needs_clarification"
        )
        == "Clarification required"
    )


def test_get_query_rows() -> None:
    rows = get_query_rows(
        build_workflow_result()
    )

    assert rows == [
        {
            "OrderCount": 830
        }
    ]


def test_get_generated_sql() -> None:
    sql = get_generated_sql(
        build_workflow_result()
    )

    assert sql is not None
    assert "SELECT" in sql
    assert "Orders" in sql


def test_get_sql_parameters() -> None:
    parameters = get_sql_parameters(
        build_workflow_result()
    )

    assert parameters == {}


def test_missing_result_data_is_safe() -> None:
    assert get_query_rows({}) == []
    assert get_generated_sql({}) is None
    assert get_sql_parameters({}) == {}