from __future__ import annotations

from typing import Any

from schemas.query_spec_schemas import (
    QueryFilter,
    QueryOperation,
    QuerySortDirection,
    QuerySpec,
)
from schemas.sql_generation_schemas import (
    GeneratedSQLQuery,
)
from semantic.query_registry import (
    DIMENSIONS,
    FILTER_FIELDS,
    METRICS,
)
from tools.join_resolver import (
    collect_relationships,
    compile_from_clause,
)


def compile_metric(
    metric_name: str,
) -> tuple[str, str, str]:
    definition = METRICS[metric_name]

    expression = definition["expression"]
    aggregation = definition["aggregation"]
    alias = definition["alias"]

    if aggregation == "SUM":
        sql = (
            f"ROUND(SUM({expression}), 2) "
            f'AS "{alias}"'
        )

    elif aggregation == "COUNT_DISTINCT":
        sql = (
            f"COUNT(DISTINCT {expression}) "
            f'AS "{alias}"'
        )

    elif aggregation == "AVERAGE_ORDER_VALUE":
        sql = (
            f"ROUND(SUM({expression}) "
            "/ NULLIF("
            "COUNT(DISTINCT o.OrderID), 0"
            "), 2) "
            f'AS "{alias}"'
        )

    else:
        raise ValueError(
            "Unsupported aggregation: "
            f"{aggregation}"
        )

    return (
        sql,
        alias,
        definition["base_table"],
    )


def compile_filter(
    query_filter: QueryFilter,
    index: int,
) -> tuple[str, dict[str, Any]]:
    expression = FILTER_FIELDS[
        query_filter.field
    ]["expression"]

    operator = query_filter.operator
    value = query_filter.value

    if operator == "equals":
        name = f"filter_{index}"

        return (
            f"{expression} = :{name}",
            {name: value},
        )

    if operator == "not_equals":
        name = f"filter_{index}"

        return (
            f"{expression} <> :{name}",
            {name: value},
        )

    if operator == "in":
        if not isinstance(
            value,
            (list, tuple),
        ):
            raise ValueError(
                "The IN operator requires a list."
            )

        if not value:
            raise ValueError(
                "The IN value list is empty."
            )

        names = []
        parameters = {}

        for value_index, member in enumerate(value):
            name = (
                f"filter_{index}_{value_index}"
            )

            names.append(f":{name}")
            parameters[name] = member

        return (
            (
                f"{expression} IN ("
                + ", ".join(names)
                + ")"
            ),
            parameters,
        )

    if operator == "between":
        if (
            not isinstance(
                value,
                (list, tuple),
            )
            or len(value) != 2
        ):
            raise ValueError(
                "BETWEEN requires two values."
            )

        lower = f"filter_{index}_lower"
        upper = f"filter_{index}_upper"

        return (
            (
                f"{expression} BETWEEN "
                f":{lower} AND :{upper}"
            ),
            {
                lower: value[0],
                upper: value[1],
            },
        )

    comparisons = {
        "greater_than": ">",
        "less_than": "<",
        "greater_than_or_equal": ">=",
        "less_than_or_equal": "<=",
    }

    if operator in comparisons:
        name = f"filter_{index}"

        return (
            (
                f"{expression} "
                f"{comparisons[operator]} "
                f":{name}"
            ),
            {name: value},
        )

    raise ValueError(
        f"Unsupported operator: {operator}"
    )


def compile_query_spec(
    query_spec: QuerySpec,
    task_id: str = "T1",
) -> GeneratedSQLQuery:
    metric_sql, metric_alias, base_table = (
        compile_metric(
            query_spec.metric
        )
    )

    select_items: list[str] = []
    group_items: list[str] = []
    expected_columns: list[str] = []

    required_tables = {
        base_table
    }

    for dimension in query_spec.dimensions:
        definition = DIMENSIONS[dimension]

        expression = definition["expression"]
        alias = definition["alias"]

        select_items.append(
            f'{expression} AS "{alias}"'
        )

        group_items.append(expression)
        expected_columns.append(alias)

        required_tables.add(
            definition["table"]
        )

    select_items.append(metric_sql)
    expected_columns.append(metric_alias)

    where_items = []
    parameters: dict[str, Any] = {}

    for index, query_filter in enumerate(
        query_spec.filters
    ):
        filter_sql, filter_parameters = (
            compile_filter(
                query_filter,
                index,
            )
        )

        where_items.append(filter_sql)
        parameters.update(filter_parameters)

        required_tables.add(
            FILTER_FIELDS[
                query_filter.field
            ]["table"]
        )

    relationships = collect_relationships(
        base_table=base_table,
        target_tables=required_tables,
    )

    from_clause = compile_from_clause(
        base_table=base_table,
        relationships=relationships,
    )

    lines = [
        "SELECT",
        "    "
        + ",\n    ".join(select_items),
        from_clause,
    ]

    if where_items:
        lines.extend(
            [
                "WHERE",
                "    "
                + "\n    AND ".join(
                    where_items
                ),
            ]
        )

    if group_items:
        lines.extend(
            [
                "GROUP BY",
                "    "
                + ",\n    ".join(
                    group_items
                ),
            ]
        )
    elif where_items:
        # An aggregate query without GROUP BY normally
        # returns one row containing NULL when no records
        # match. HAVING converts that into zero rows so
        # the workflow can return status=no_data.
        lines.append(
            "HAVING COUNT(*) > 0"
        )

    if QueryOperation.RANK in (
        query_spec.operations
    ):
        direction = "DESC"

        if (
            query_spec.sort_direction
            == QuerySortDirection.ASCENDING
        ):
            direction = "ASC"

        lines.extend(
            [
                "ORDER BY",
                (
                    f'    "{metric_alias}" '
                    f"{direction}"
                ),
            ]
        )

    elif QueryOperation.TREND in (
        query_spec.operations
    ):
        order_aliases = [
            DIMENSIONS[dimension]["alias"]
            for dimension
            in query_spec.dimensions
        ]

        if order_aliases:
            lines.extend(
                [
                    "ORDER BY",
                    "    "
                    + ", ".join(
                        f'"{alias}"'
                        for alias in order_aliases
                    ),
                ]
            )

    if query_spec.limit is not None:
        lines.append(
            f"LIMIT {query_spec.limit}"
        )

    return GeneratedSQLQuery(
        task_id=task_id,
        sql="\n".join(lines),
        parameters=parameters,
        referenced_tables=sorted(
            required_tables
        ),
        expected_columns=expected_columns,
        explanation=(
            "Compiled deterministically from a "
            "validated QuerySpec."
        ),
        assumptions=[],
    )