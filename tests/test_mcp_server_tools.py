from mcp_servers.analytics_server import (
    compile_analytical_query,
    get_dimension_definition,
    get_metric_definition,
    list_capabilities,
    rank_records,
    validate_read_only_sql,
)


def test_list_capabilities() -> None:
    result = list_capabilities()

    assert result["success"] is True
    assert "net_revenue" in (
        result["data"]["metrics"]
    )
    assert "category" in (
        result["data"]["dimensions"]
    )


def test_get_metric_definition() -> None:
    result = get_metric_definition(
        "net_revenue"
    )

    assert result["success"] is True
    assert result["data"]["alias"] == (
        "NetRevenue"
    )
    assert result["data"]["base_table"] == (
        "Order Details"
    )


def test_get_dimension_definition() -> None:
    result = get_dimension_definition(
        "category"
    )

    assert result["success"] is True
    assert result["data"]["alias"] == (
        "CategoryName"
    )


def test_compile_analytical_query() -> None:
    result = compile_analytical_query(
        query_spec={
            "metric": "net_revenue",
            "dimensions": [
                "category"
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

    assert query["expected_columns"] == [
        "CategoryName",
        "NetRevenue",
    ]

    assert "LIMIT 5" in query["sql"]


def test_unsafe_sql_is_rejected() -> None:
    result = validate_read_only_sql(
        "DROP TABLE Orders"
    )

    assert result["success"] is False


def test_rank_records() -> None:
    result = rank_records(
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

    assert records[0]["label"] == (
        "Beverages"
    )
    assert records[0]["rank"] == 1