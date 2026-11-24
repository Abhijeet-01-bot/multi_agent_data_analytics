from __future__ import annotations

import json

from mcp_clients.analytics_client import (
    AnalyticsMCPClient,
)


def print_section(
    title: str,
    value: object,
) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("-" * 80)

    print(
        json.dumps(
            value,
            indent=2,
            default=str,
        )
    )


def main() -> None:
    client = AnalyticsMCPClient(
        timeout_seconds=30.0
    )

    tools = client.list_tools()

    print_section(
        "DISCOVERED MCP TOOLS",
        tools,
    )

    capabilities = (
        client.list_capabilities()
    )

    print_section(
        "CAPABILITIES",
        capabilities,
    )

    compiled = client.compile_query(
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

    print_section(
        "COMPILED QUERY",
        compiled,
    )

    if not compiled.get(
        "success",
        False,
    ):
        return

    query = compiled[
        "data"
    ]["query"]

    executed = client.execute_query(
        sql=query["sql"],
        parameters=query[
            "parameters"
        ],
    )

    print_section(
        "EXECUTED QUERY",
        executed,
    )

    unsafe = client.validate_sql(
        "DROP TABLE Orders"
    )

    print_section(
        "UNSAFE SQL VALIDATION",
        unsafe,
    )

    ranked = client.rank_rows(
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

    print_section(
        "RANKED RECORDS",
        ranked,
    )


if __name__ == "__main__":
    main()