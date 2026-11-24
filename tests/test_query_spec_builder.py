from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
)
from schemas.query_spec_schemas import (
    QueryOperation,
)
from semantic.query_spec_builder import (
    build_query_spec,
)


def test_category_in_filter_builds_query_spec() -> None:
    intent = IntentResult(
        business_objective=(
            "Compare monthly sales for "
            "Beverages and Dairy Products."
        ),
        metrics=[
            "net_revenue"
        ],
        dimensions=[
            "category",
            "order_month",
        ],
        filters=[
            IntentFilter(
                field="category",
                operator="in",
                value=[
                    "Beverages",
                    "Dairy Products",
                ],
            )
        ],
        analysis_types=[
            AnalysisType.AGGREGATION,
            AnalysisType.COMPARISON,
            AnalysisType.TREND,
        ],
        sort_direction=None,
        limit=None,
        confidence=1.0,
    )

    specification = build_query_spec(
        intent
    )

    assert specification.metric == (
        "net_revenue"
    )

    assert set(
        specification.dimensions
    ) == {
        "category",
        "order_month",
    }

    assert len(
        specification.filters
    ) == 1

    category_filter = (
        specification.filters[0]
    )

    assert category_filter.field == (
        "category"
    )

    assert category_filter.operator == (
        "in"
    )

    assert category_filter.value == [
        "Beverages",
        "Dairy Products",
    ]

    assert (
        QueryOperation.COMPARE
        in specification.operations
    )

    assert (
        QueryOperation.TREND
        in specification.operations
    )