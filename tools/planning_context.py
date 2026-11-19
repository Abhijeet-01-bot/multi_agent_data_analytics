from __future__ import annotations

from typing import Any

from schemas.intent_schemas import IntentResult
from tools.schema_loader import (
    load_metric_definitions,
    load_schema_catalog,
)


DIMENSION_MAPPINGS = {
    "category": {
        "table": "Categories",
        "column": "CategoryName",
    },
    "product": {
        "table": "Products",
        "column": "ProductName",
    },
    "customer": {
        "table": "Customers",
        "column": "CompanyName",
    },
    "customer_country": {
        "table": "Customers",
        "column": "Country",
    },
    "ship_country": {
        "table": "Orders",
        "column": "ShipCountry",
    },
    "supplier": {
        "table": "Suppliers",
        "column": "CompanyName",
    },
    "employee": {
        "table": "Employees",
        "column": "EmployeeID",
    },
    "order_date": {
        "table": "Orders",
        "column": "OrderDate",
    },
    "order_month": {
        "table": "Orders",
        "column": "OrderDate",
        "transformation": (
            "Use SQLite STRFTIME('%Y-%m', OrderDate)."
        ),
    },
    "order_quarter": {
        "table": "Orders",
        "column": "OrderDate",
        "transformation": (
            "Derive quarter from the OrderDate month."
        ),
    },
    "order_year": {
        "table": "Orders",
        "column": "OrderDate",
        "transformation": (
            "Use SQLite STRFTIME('%Y', OrderDate)."
        ),
    },
}


FILTER_FIELD_MAPPINGS = {
    "category": {
        "table": "Categories",
        "column": "CategoryName",
    },
    "product": {
        "table": "Products",
        "column": "ProductName",
    },
    "customer": {
        "table": "Customers",
        "column": "CompanyName",
    },
    "customer_country": {
        "table": "Customers",
        "column": "Country",
    },
    "ship_country": {
        "table": "Orders",
        "column": "ShipCountry",
    },
    "supplier": {
        "table": "Suppliers",
        "column": "CompanyName",
    },
    "employee": {
        "table": "Employees",
        "column": "EmployeeID",
    },
    "order_date": {
        "table": "Orders",
        "column": "OrderDate",
    },
    "discount": {
        "table": "Order Details",
        "column": "Discount",
    },
}


def get_metric_planning_context(
    metric_names: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Return complete definitions for metrics requested
    in the analytical intent.
    """

    metric_data = load_metric_definitions()
    all_metrics = metric_data.get(
        "metrics",
        {},
    )

    return {
        metric_name: all_metrics[metric_name]
        for metric_name in metric_names
        if metric_name in all_metrics
    }


def get_dimension_planning_context(
    dimension_names: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Resolve canonical dimensions to physical database
    columns.
    """

    return {
        dimension_name: DIMENSION_MAPPINGS[
            dimension_name
        ]
        for dimension_name in dimension_names
        if dimension_name in DIMENSION_MAPPINGS
    }


def get_filter_planning_context(
    intent: IntentResult,
) -> dict[str, dict[str, Any]]:
    """
    Resolve the filter fields from an intent to
    physical database fields.
    """

    resolved_filters: dict[
        str,
        dict[str, Any],
    ] = {}

    for intent_filter in intent.filters:
        field_name = intent_filter.field

        if field_name in FILTER_FIELD_MAPPINGS:
            resolved_filters[field_name] = {
                **FILTER_FIELD_MAPPINGS[
                    field_name
                ],
                "operator": (
                    intent_filter.operator.value
                ),
                "value": intent_filter.value,
            }

    return resolved_filters


def get_relevant_tables(
    intent: IntentResult,
) -> list[str]:
    """
    Identify tables directly required by the intent's
    dimensions and filters.

    Metric source tables are added from metric metadata
    where available.
    """

    tables: set[str] = set()

    dimension_context = (
        get_dimension_planning_context(
            intent.dimensions
        )
    )

    for mapping in dimension_context.values():
        tables.add(mapping["table"])

    filter_context = get_filter_planning_context(
        intent
    )

    for mapping in filter_context.values():
        tables.add(mapping["table"])

    metric_context = get_metric_planning_context(
        intent.metrics
    )

    for definition in metric_context.values():
        source_table = definition.get(
            "source_table"
        )

        if source_table:
            tables.add(source_table)

        source_tables = definition.get(
            "source_tables",
            [],
        )

        tables.update(source_tables)

    return sorted(tables)


def build_planning_context(
    intent: IntentResult,
) -> dict[str, Any]:
    """
    Build grounded planning information from the
    semantic layer and structured intent.
    """

    catalog = load_schema_catalog()

    relevant_table_names = get_relevant_tables(
        intent
    )

    table_catalog = catalog.get(
        "tables",
        {},
    )

    relevant_table_context = {
        table_name: table_catalog[table_name]
        for table_name in relevant_table_names
        if table_name in table_catalog
    }

    return {
        "metrics": get_metric_planning_context(
            intent.metrics
        ),
        "dimensions": (
            get_dimension_planning_context(
                intent.dimensions
            )
        ),
        "filters": get_filter_planning_context(
            intent
        ),
        "directly_relevant_tables": (
            relevant_table_context
        ),
        "all_available_tables": list(
            table_catalog.keys()
        ),
        "relationships": catalog.get(
            "relationships",
            [],
        ),
        "database_dialect": catalog.get(
            "database_dialect",
            "sqlite",
        ),
    }