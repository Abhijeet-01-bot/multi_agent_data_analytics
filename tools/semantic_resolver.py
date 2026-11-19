from __future__ import annotations

from typing import Any

from tools.schema_loader import (
    load_business_glossary,
    load_metric_definitions,
    load_schema_catalog,
)


def get_available_metrics() -> dict[str, dict[str, Any]]:
    """
    Return all approved metric definitions.
    """

    metric_data = load_metric_definitions()

    return metric_data.get("metrics", {})


def get_glossary_terms() -> dict[str, dict[str, Any]]:
    """
    Return all business glossary mappings.
    """

    glossary_data = load_business_glossary()

    return glossary_data.get("terms", {})


def get_available_tables() -> dict[str, dict[str, Any]]:
    """
    Return table metadata from the schema catalog.
    """

    catalog = load_schema_catalog()

    return catalog.get("tables", {})


def resolve_business_term(
    term: str,
) -> dict[str, Any] | None:
    """
    Resolve a business-language term using the glossary.

    The match is case-insensitive.
    """

    normalized_term = term.strip().lower()
    glossary_terms = get_glossary_terms()

    for glossary_term, mapping in glossary_terms.items():
        if glossary_term.lower() == normalized_term:
            return {
                "term": glossary_term,
                **mapping,
            }

    return None


def build_intent_context() -> dict[str, Any]:
    """
    Build compact semantic context for the Intent Agent.
    """

    metrics = get_available_metrics()
    glossary = get_glossary_terms()
    tables = get_available_tables()

    metric_context = {
        metric_name: {
            "display_name": definition.get(
                "display_name"
            ),
            "description": definition.get(
                "description"
            ),
        }
        for metric_name, definition in metrics.items()
    }

    glossary_context = {
        term: mapping
        for term, mapping in glossary.items()
    }

    table_context = {
        table_name: metadata.get("description")
        for table_name, metadata in tables.items()
    }

    return {
        "metrics": metric_context,
        "glossary": glossary_context,
        "tables": table_context,
        "supported_dimensions": [
            "category",
            "product",
            "customer",
            "customer_country",
            "ship_country",
            "supplier",
            "employee",
            "order_date",
            "order_month",
            "order_quarter",
            "order_year",
        ],
    }