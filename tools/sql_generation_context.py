from __future__ import annotations

from typing import Any

from schemas.intent_schemas import IntentResult
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
)
from tools.planning_context import (
    FILTER_FIELD_MAPPINGS,
    DIMENSION_MAPPINGS,
)
from tools.schema_loader import (
    load_metric_definitions,
    load_schema_catalog,
)


def get_task_metric_context(
    task: AnalyticalTask,
) -> dict[str, dict[str, Any]]:
    """
    Return the complete semantic definitions for metrics
    required by the current task.
    """

    metric_data = load_metric_definitions()
    all_metrics = metric_data.get(
        "metrics",
        {},
    )

    return {
        metric_name: all_metrics[metric_name]
        for metric_name in task.metrics
        if metric_name in all_metrics
    }


def get_task_dimension_context(
    task: AnalyticalTask,
) -> dict[str, dict[str, Any]]:
    """
    Resolve task dimensions to physical columns and
    transformations.
    """

    return {
        dimension: DIMENSION_MAPPINGS[dimension]
        for dimension in task.dimensions
        if dimension in DIMENSION_MAPPINGS
    }


def get_task_filter_context(
    task: AnalyticalTask,
) -> list[dict[str, Any]]:
    """
    Resolve each task filter to its physical database
    table and column.
    """

    resolved_filters: list[dict[str, Any]] = []

    for task_filter in task.filters:
        field = task_filter.field
        mapping = FILTER_FIELD_MAPPINGS.get(field)

        if mapping is None:
            continue

        resolved_filters.append(
            {
                "field": field,
                "table": mapping["table"],
                "column": mapping["column"],
                "operator": task_filter.operator,
                "value": task_filter.value,
            }
        )

    return resolved_filters


def get_required_table_context(
    plan: ExecutionPlan,
    task: AnalyticalTask,
) -> dict[str, Any]:
    """
    Return schema information for tables required by
    either the current task or the overall plan.
    """

    catalog = load_schema_catalog()
    all_tables = catalog.get("tables", {})

    required_table_names = set(
        plan.required_tables
    )

    required_table_names.update(
        task.required_tables
    )

    return {
        table_name: all_tables[table_name]
        for table_name in sorted(
            required_table_names
        )
        if table_name in all_tables
    }


def get_required_join_context(
    plan: ExecutionPlan,
) -> list[dict[str, Any]]:
    """
    Convert the approved plan joins into dictionaries
    suitable for the SQL Agent prompt.
    """

    return [
        join.model_dump(
            mode="json"
        )
        for join in plan.required_joins
    ]


def build_sql_generation_context(
    intent: IntentResult,
    plan: ExecutionPlan,
    task: AnalyticalTask,
) -> dict[str, Any]:
    """
    Build grounded SQL-generation context for one
    analytical task.
    """

    catalog = load_schema_catalog()

    return {
        "database_dialect": catalog.get(
            "database_dialect",
            "sqlite",
        ),
        "business_objective": (
            intent.business_objective
        ),
        "current_task": task.model_dump(
            mode="json"
        ),
        "metric_definitions": (
            get_task_metric_context(task)
        ),
        "dimension_mappings": (
            get_task_dimension_context(task)
        ),
        "filter_mappings": (
            get_task_filter_context(task)
        ),
        "required_tables": (
            get_required_table_context(
                plan,
                task,
            )
        ),
        "required_joins": (
            get_required_join_context(plan)
        ),
        "expected_columns": (
            task.expected_columns
        ),
        "sort_direction": (
            intent.sort_direction.value
            if intent.sort_direction
            else None
        ),
        "limit": intent.limit,
        "time_range": (
            intent.time_range.model_dump(
                mode="json"
            )
            if intent.time_range
            else None
        ),
        "sql_rules": [
            (
                "Generate exactly one read-only "
                "SQLite SELECT statement."
            ),
            (
                "Use named parameters for user "
                "filter values."
            ),
            (
                "Return parameters separately from SQL."
            ),
            (
                "Quote table names containing spaces "
                "with double quotes."
            ),
            (
                "Use only supplied tables, columns, "
                "metrics, and joins."
            ),
            (
                "Do not use SELECT *."
            ),
            
            "Alias calculated metrics using the "
            "expected output names.",
        ],
    }