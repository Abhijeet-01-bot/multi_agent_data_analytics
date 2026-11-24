from config.settings import settings
from services.analytics_gateway import (
    AnalyticsGateway,
)


QUERY_SPEC = {
    "metric": "net_revenue",
    "dimensions": [
        "category",
    ],
    "filters": [],
    "operations": [
        "aggregate",
        "rank",
    ],
    "sort_direction": "descending",
    "limit": 5,
}


def test_gateway_direct_compilation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "mcp_enabled",
        False,
    )

    gateway = AnalyticsGateway()

    result = gateway.compile_query(
        query_spec=QUERY_SPEC,
        task_id="T1",
    )

    assert result["success"] is True

    assert result[
        "data"
    ]["query"][
        "expected_columns"
    ] == [
        "CategoryName",
        "NetRevenue",
    ]

    if "backend" in result:
        assert result["backend"] == (
            "direct"
        )


def test_gateway_mcp_compilation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "mcp_enabled",
        True,
    )

    monkeypatch.setattr(
        settings,
        "mcp_fallback_to_direct",
        True,
    )

    gateway = AnalyticsGateway()

    fake_result = {
        "success": True,
        "data": {
            "query": {
                "task_id": "T1",
                "sql": (
                    "SELECT COUNT(*) "
                    'AS "OrderCount" '
                    "FROM Orders"
                ),
                "parameters": {},
                "referenced_tables": [
                    "Orders"
                ],
                "expected_columns": [
                    "OrderCount"
                ],
                "explanation": (
                    "Test query."
                ),
                "assumptions": [],
            },
            "validation": {},
        },
        "errors": [],
        "warnings": [],
    }

    monkeypatch.setattr(
        gateway.mcp_client,
        "compile_query",
        lambda query_spec, task_id: (
            dict(fake_result)
        ),
    )

    result = gateway.compile_query(
        query_spec=QUERY_SPEC,
        task_id="T1",
    )

    assert result["success"] is True

    if "backend" in result:
        assert result["backend"] == (
            "mcp"
        )


def test_gateway_execution_falls_back(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "mcp_enabled",
        True,
    )

    monkeypatch.setattr(
        settings,
        "mcp_fallback_to_direct",
        True,
    )

    gateway = AnalyticsGateway()

    monkeypatch.setattr(
        gateway.mcp_client,
        "execute_query",
        (
            lambda sql, parameters: {
                "success": False,
                "data": None,
                "errors": [
                    "Simulated MCP failure."
                ],
                "warnings": [],
            }
        ),
    )

    result = gateway.execute_query(
        sql=(
            "SELECT "
            "COUNT(*) AS OrderCount "
            "FROM Orders"
        ),
        parameters={},
    )

    assert result["success"] is True

    if "backend" in result:
        assert result["backend"] == (
            "direct_fallback"
        )

    assert any(
        "direct executor was used"
        in warning
        for warning in result.get(
            "warnings",
            [],
        )
    )