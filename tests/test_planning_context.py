from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
    SortDirection,
)
from tools.planning_context import (
    build_planning_context,
    get_dimension_planning_context,
    get_filter_planning_context,
    get_metric_planning_context,
    get_relevant_tables,
)


def build_sample_intent() -> IntentResult:
    return IntentResult(
        business_objective=(
            "Rank product categories by net revenue "
            "for orders shipped to Germany."
        ),
        metrics=["net_revenue"],
        dimensions=["category"],
        filters=[
            IntentFilter(
                field="ship_country",
                operator="equals",
                value="Germany",
            )
        ],
        analysis_types=[
            AnalysisType.AGGREGATION,
            AnalysisType.RANKING,
        ],
        sort_direction=SortDirection.DESCENDING,
        limit=5,
        confidence=1.0,
    )


def test_metric_planning_context() -> None:
    context = get_metric_planning_context(
        ["net_revenue"]
    )

    assert "net_revenue" in context

    metric = context["net_revenue"]

    assert metric["source_table"] == (
        "Order Details"
    )

    assert "UnitPrice" in metric[
        "source_columns"
    ]

    assert "Quantity" in metric[
        "source_columns"
    ]

    assert "Discount" in metric[
        "source_columns"
    ]


def test_dimension_planning_context() -> None:
    context = get_dimension_planning_context(
        ["category", "order_month"]
    )

    assert context["category"]["table"] == (
        "Categories"
    )

    assert context["category"]["column"] == (
        "CategoryName"
    )

    assert context["order_month"]["table"] == (
        "Orders"
    )

    assert "transformation" in context[
        "order_month"
    ]


def test_filter_planning_context() -> None:
    intent = build_sample_intent()

    context = get_filter_planning_context(
        intent
    )

    assert "ship_country" in context

    ship_country = context["ship_country"]

    assert ship_country["table"] == "Orders"
    assert ship_country["column"] == "ShipCountry"
    assert ship_country["operator"] == "equals"
    assert ship_country["value"] == "Germany"


def test_relevant_tables() -> None:
    intent = build_sample_intent()

    tables = get_relevant_tables(intent)

    assert "Order Details" in tables
    assert "Categories" in tables
    assert "Orders" in tables


def test_build_planning_context() -> None:
    intent = build_sample_intent()

    context = build_planning_context(intent)

    assert context["database_dialect"] == "sqlite"
    assert "metrics" in context
    assert "dimensions" in context
    assert "filters" in context
    assert "relationships" in context

    assert "net_revenue" in context["metrics"]
    assert "category" in context["dimensions"]
    assert "ship_country" in context["filters"]

    assert len(context["relationships"]) > 0