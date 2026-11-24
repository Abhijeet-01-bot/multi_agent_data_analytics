from __future__ import annotations

from semantic.query_registry import (
    DIMENSIONS,
    FILTER_FIELDS,
    METRICS,
)
from schemas.query_spec_schemas import (
    QuerySpec,
)
from tools.analytics_tools import (
    analyze_ranking,
)
from tools.query_compiler import (
    compile_query_spec,
)
from tools.query_executor import (
    execute_read_only_query,
)
from tools.sql_validator import (
    validate_sql,
)


def success_response(
    data: object,
    warnings: list[str] | None = None,
) -> dict:
    """
    Return a consistent successful MCP service response.
    """

    return {
        "success": True,
        "data": data,
        "errors": [],
        "warnings": warnings or [],
    }


def error_response(
    *errors: str,
) -> dict:
    """
    Return a consistent failed MCP service response.
    """

    return {
        "success": False,
        "data": None,
        "errors": list(errors),
        "warnings": [],
    }


def list_capabilities_service() -> dict:
    """
    Return metrics, dimensions, filter fields, and
    analytical operations supported by the application.
    """

    return success_response(
        {
            "metrics": sorted(
                METRICS.keys()
            ),
            "dimensions": sorted(
                DIMENSIONS.keys()
            ),
            "filter_fields": sorted(
                FILTER_FIELDS.keys()
            ),
            "operations": [
                "aggregate",
                "rank",
                "compare",
                "trend",
            ],
        }
    )


def get_metric_definition_service(
    metric_name: str,
) -> dict:
    """
    Return one approved metric definition.
    """

    definition = METRICS.get(
        metric_name
    )

    if definition is None:
        return error_response(
            f"Unknown metric: {metric_name}"
        )

    return success_response(
        {
            "metric_name": metric_name,
            **definition,
        }
    )


def get_dimension_definition_service(
    dimension_name: str,
) -> dict:
    """
    Return one approved dimension definition.
    """

    definition = DIMENSIONS.get(
        dimension_name
    )

    if definition is None:
        return error_response(
            (
                "Unknown dimension: "
                f"{dimension_name}"
            )
        )

    return success_response(
        {
            "dimension_name": (
                dimension_name
            ),
            **definition,
        }
    )


def compile_query_service(
    query_spec: dict,
    task_id: str = "T1",
) -> dict:
    """
    Validate a QuerySpec and compile it into safe,
    parameterized SQLite SQL.
    """

    try:
        specification = (
            QuerySpec.model_validate(
                query_spec
            )
        )

        query = compile_query_spec(
            query_spec=specification,
            task_id=task_id,
        )

        validation = validate_sql(
            query.sql
        )

        if not validation.is_valid:
            return error_response(
                *validation.errors
            )

        return success_response(
            {
                "query": query.model_dump(
                    mode="json"
                ),
                "validation": (
                    validation.model_dump(
                        mode="json"
                    )
                ),
            },
            warnings=validation.warnings,
        )

    except Exception as error:
        return error_response(
            str(error)
        )


def validate_sql_service(
    sql: str,
) -> dict:
    """
    Validate SQL without executing it.
    """

    try:
        result = validate_sql(
            sql
        )

        return {
            "success": result.is_valid,
            "data": result.model_dump(
                mode="json"
            ),
            "errors": result.errors,
            "warnings": result.warnings,
        }

    except Exception as error:
        return error_response(
            str(error)
        )


def execute_query_service(
    sql: str,
    parameters: dict | None = None,
) -> dict:
    """
    Validate and execute one read-only SQL query.
    """

    try:
        validation = validate_sql(
            sql
        )

        if not validation.is_valid:
            return error_response(
                *validation.errors
            )

        execution = (
            execute_read_only_query(
                sql=sql,
                parameters=(
                    parameters or {}
                ),
            )
        )

        return {
            "success": (
                execution.success
            ),
            "data": execution.model_dump(
                mode="json"
            ),
            "errors": execution.errors,
            "warnings": (
                execution.warnings
            ),
        }

    except Exception as error:
        return error_response(
            str(error)
        )


def rank_records_service(
    rows: list[dict],
    label_column: str,
    value_column: str,
    descending: bool = True,
    limit: int | None = None,
) -> dict:
    """
    Rank validated records through the deterministic
    analytics layer.
    """

    try:
        result = analyze_ranking(
            rows=rows,
            label_column=label_column,
            value_column=value_column,
            descending=descending,
            limit=limit,
        )

        return {
            "success": result.success,
            "data": result.model_dump(
                mode="json"
            ),
            "errors": result.errors,
            "warnings": result.warnings,
        }

    except Exception as error:
        return error_response(
            str(error)
        )