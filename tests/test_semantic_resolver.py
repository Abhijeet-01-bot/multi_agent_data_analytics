from tools.semantic_resolver import (
    build_intent_context,
    get_available_metrics,
    get_available_tables,
    get_glossary_terms,
    resolve_business_term,
)


def test_available_metrics() -> None:
    metrics = get_available_metrics()

    assert "net_revenue" in metrics
    assert "gross_revenue" in metrics
    assert "order_count" in metrics


def test_available_tables() -> None:
    tables = get_available_tables()

    assert "Customers" in tables
    assert "Orders" in tables
    assert "Order Details" in tables
    assert "Products" in tables
    assert "Categories" in tables


def test_glossary_terms() -> None:
    glossary = get_glossary_terms()

    assert "sales" in glossary
    assert "revenue" in glossary
    assert "customers" in glossary


def test_resolve_sales_term() -> None:
    result = resolve_business_term("sales")

    assert result is not None
    assert result["metric"] == "net_revenue"


def test_resolve_term_is_case_insensitive() -> None:
    result = resolve_business_term("Revenue")

    assert result is not None
    assert result["metric"] == "net_revenue"


def test_unknown_term_returns_none() -> None:
    result = resolve_business_term(
        "stock_market_price"
    )

    assert result is None


def test_build_intent_context() -> None:
    context = build_intent_context()

    assert "metrics" in context
    assert "glossary" in context
    assert "tables" in context
    assert "supported_dimensions" in context

    assert "net_revenue" in context["metrics"]
    assert "category" in context[
        "supported_dimensions"
    ]