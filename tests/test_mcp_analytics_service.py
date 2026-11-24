from services.mcp_analytics_service import (
    compile_query_service,
    execute_query_service,
    get_dimension_definition_service,
    get_metric_definition_service,
    list_capabilities_service,
    rank_records_service,
    validate_sql_service,
)


def test_capabilities_service() -> None:
    result = list_capabilities_service()

    assert result["success"] is True
    assert "net_revenue" in result[
        "data"
    ]["metrics"]
    assert "category" in result[
        "data"
    ]["dimensions"]


def test_metric_definition_service() -> None:
    result = (
        get_metric_definition_service(
            "net_revenue"
        )
    )

    assert result["success"] is True
    assert result["data"]["alias"] == (
        "NetRevenue"
    )
    assert result["data"]["base_table"] == (
        "Order Details"
    )


def test_dimension_definition_service() -> None:
    result = (
        get_dimension_definition_service(
            "category"
        )
    )

    assert result["success"] is True
    assert result["data"]["alias"] == (
        "CategoryName"
    )


def test_compile_query_service() -> None:
    result = compile_query_service(
        query_spec={
            "metric": "net_revenue",
            "dimensions": [
                "category",
            ],
            "filters": [],
            "operations": [
                "aggregate",
                "rank",
            ],
            "sort_direction": (
                "descending"
            ),
            "limit": 5,
        },
        task_id="T1",
    )

    assert result["success"] is True

    query = result["data"]["query"]

    assert query[
        "expected_columns"
    ] == [
        "CategoryName",
        "NetRevenue",
    ]

    assert "LIMIT 5" in query["sql"]


def test_execute_query_service() -> None:
    result = execute_query_service(
        sql=(
            "SELECT "
            "COUNT(*) AS OrderCount "
            "FROM Orders"
        ),
        parameters={},
    )

    assert result["success"] is True

    execution = result["data"]

    assert execution["success"] is True
    assert execution["status"] == (
        "completed"
    )
    assert execution["columns"] == [
        "OrderCount"
    ]
    assert len(execution["rows"]) == 1
    assert (
        execution["rows"][0][
            "OrderCount"
        ]
        > 0
    )


def test_compile_and_execute_service() -> None:
    compiled = compile_query_service(
        query_spec={
            "metric": "net_revenue",
            "dimensions": [
                "category",
            ],
            "filters": [],
            "operations": [
                "aggregate",
                "rank",
            ],
            "sort_direction": (
                "descending"
            ),
            "limit": 5,
        },
        task_id="T1",
    )

    assert compiled["success"] is True

    query = compiled[
        "data"
    ]["query"]

    executed = execute_query_service(
        sql=query["sql"],
        parameters=query[
            "parameters"
        ],
    )

    assert executed["success"] is True
    assert executed[
        "data"
    ]["columns"] == [
        "CategoryName",
        "NetRevenue",
    ]
    assert len(
        executed["data"]["rows"]
    ) == 5


def test_unsafe_sql_is_rejected() -> None:
    result = validate_sql_service(
        "DROP TABLE Orders"
    )

    assert result["success"] is False
    assert result["errors"]


def test_ranking_service() -> None:
    result = rank_records_service(
        rows=[
            {
                "CategoryName": (
                    "Beverages"
                ),
                "NetRevenue": 1000,
            },
            {
                "CategoryName": (
                    "Seafood"
                ),
                "NetRevenue": 800,
            },
        ],
        label_column="CategoryName",
        value_column="NetRevenue",
        descending=True,
        limit=2,
    )

    assert result["success"] is True

    records = result[
        "data"
    ]["records"]

    assert records[0]["rank"] == 1
    assert records[0]["label"] == (
        "Beverages"
    )
    assert records[1]["rank"] == 2