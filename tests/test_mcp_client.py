from mcp_clients.analytics_client import (
    AnalyticsMCPClient,
)


def build_client() -> AnalyticsMCPClient:
    return AnalyticsMCPClient(
        timeout_seconds=30.0
    )


def test_mcp_client_discovers_tools() -> None:
    client = build_client()

    tools = client.list_tools()

    assert "list_capabilities" in tools
    assert (
        "compile_analytical_query"
        in tools
    )
    assert (
        "execute_validated_query"
        in tools
    )
    assert "rank_records" in tools


def test_mcp_client_lists_capabilities() -> None:
    result = (
        build_client()
        .list_capabilities()
    )

    assert result["success"] is True
    assert "net_revenue" in result[
        "data"
    ]["metrics"]


def test_mcp_client_compiles_query() -> None:
    result = (
        build_client().compile_query(
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
    )

    assert result["success"] is True

    query = result[
        "data"
    ]["query"]

    assert query[
        "expected_columns"
    ] == [
        "CategoryName",
        "NetRevenue",
    ]


def test_mcp_client_executes_query() -> None:
    result = (
        build_client().execute_query(
            sql=(
                "SELECT "
                "COUNT(*) AS OrderCount "
                "FROM Orders"
            ),
            parameters={},
        )
    )

    assert result["success"] is True

    execution = result["data"]

    assert execution["status"] == (
        "completed"
    )
    assert execution["columns"] == [
        "OrderCount"
    ]
    assert len(execution["rows"]) == 1


def test_mcp_client_rejects_unsafe_sql() -> None:
    result = (
        build_client().validate_sql(
            "DROP TABLE Orders"
        )
    )

    assert result["success"] is False
    assert result["errors"]


def test_mcp_client_ranks_rows() -> None:
    result = (
        build_client().rank_rows(
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
            label_column=(
                "CategoryName"
            ),
            value_column="NetRevenue",
            descending=True,
            limit=2,
        )
    )

    assert result["success"] is True

    records = result[
        "data"
    ]["records"]

    assert records[0]["label"] == (
        "Beverages"
    )