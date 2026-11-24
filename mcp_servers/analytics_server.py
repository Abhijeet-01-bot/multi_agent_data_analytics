from __future__ import annotations

from mcp.server import MCPServer

from semantic.query_registry import (
    DIMENSIONS,
    METRICS,
    RELATIONSHIPS,
)
from services.mcp_analytics_service import (
    compile_query_service,
    execute_query_service,
    get_dimension_definition_service,
    get_metric_definition_service,
    list_capabilities_service,
    rank_records_service,
    validate_sql_service,
)


mcp = MCPServer(
    "Northwind Analytics"
)


@mcp.tool()
def list_capabilities() -> dict:
    """
    Return supported analytics capabilities.
    """

    return list_capabilities_service()


@mcp.tool()
def get_metric_definition(
    metric_name: str,
) -> dict:
    """
    Return one approved metric definition.
    """

    return get_metric_definition_service(
        metric_name
    )


@mcp.tool()
def get_dimension_definition(
    dimension_name: str,
) -> dict:
    """
    Return one approved dimension definition.
    """

    return (
        get_dimension_definition_service(
            dimension_name
        )
    )


@mcp.tool()
def compile_analytical_query(
    query_spec: dict,
    task_id: str = "T1",
) -> dict:
    """
    Compile a QuerySpec into validated, read-only
    SQLite SQL.
    """

    return compile_query_service(
        query_spec=query_spec,
        task_id=task_id,
    )


@mcp.tool()
def validate_read_only_sql(
    sql: str,
) -> dict:
    """
    Validate SQL without executing it.
    """

    return validate_sql_service(
        sql
    )


@mcp.tool()
def execute_validated_query(
    sql: str,
    parameters: dict | None = None,
) -> dict:
    """
    Validate and execute one read-only SQL query.
    """

    return execute_query_service(
        sql=sql,
        parameters=parameters,
    )


@mcp.tool()
def rank_records(
    rows: list[dict],
    label_column: str,
    value_column: str,
    descending: bool = True,
    limit: int | None = None,
) -> dict:
    """
    Rank validated records deterministically.
    """

    return rank_records_service(
        rows=rows,
        label_column=label_column,
        value_column=value_column,
        descending=descending,
        limit=limit,
    )


@mcp.resource(
    "northwind://semantic/metrics"
)
def metrics_resource() -> dict:
    """
    Return all approved metric definitions.
    """

    return METRICS


@mcp.resource(
    "northwind://semantic/dimensions"
)
def dimensions_resource() -> dict:
    """
    Return all approved dimension definitions.
    """

    return DIMENSIONS


@mcp.resource(
    "northwind://semantic/relationships"
)
def relationships_resource() -> list:
    """
    Return approved Northwind table relationships.
    """

    return RELATIONSHIPS


if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )