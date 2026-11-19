from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
    SortDirection,
)
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
    RequiredJoin,
    TaskType,
)
from tools.sql_generation_context import (
    build_sql_generation_context,
    get_required_table_context,
    get_task_dimension_context,
    get_task_filter_context,
    get_task_metric_context,
)


def build_test_intent() -> IntentResult:
    return IntentResult(
        business_objective=(
            "Rank categories by net revenue in Germany."
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


def build_test_task() -> AnalyticalTask:
    return AnalyticalTask(
        task_id="T1",
        description=(
            "Calculate category net revenue for "
            "orders shipped to Germany."
        ),
        task_type=TaskType.DATA_RETRIEVAL,
        metrics=["net_revenue"],
        dimensions=["category"],
        filters=[
            {
                "field": "ship_country",
                "operator": "equals",
                "value": "Germany",
            }
        ],
        required_tables=[
            "Orders",
            "Order Details",
            "Products",
            "Categories",
        ],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
    )


def build_test_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_summary=(
            "Calculate and rank category revenue."
        ),
        tasks=[
            build_test_task()
        ],
        required_tables=[
            "Orders",
            "Order Details",
            "Products",
            "Categories",
        ],
        required_joins=[
            RequiredJoin(
                left_table="Orders",
                left_column="OrderID",
                right_table="Order Details",
                right_column="OrderID",
            ),
            RequiredJoin(
                left_table="Order Details",
                left_column="ProductID",
                right_table="Products",
                right_column="ProductID",
            ),
            RequiredJoin(
                left_table="Products",
                left_column="CategoryID",
                right_table="Categories",
                right_column="CategoryID",
            ),
        ],
        confidence=1.0,
    )


def test_task_metric_context() -> None:
    context = get_task_metric_context(
        build_test_task()
    )

    assert "net_revenue" in context
    assert context["net_revenue"][
        "source_table"
    ] == "Order Details"


def test_task_dimension_context() -> None:
    context = get_task_dimension_context(
        build_test_task()
    )

    assert context["category"]["table"] == (
        "Categories"
    )

    assert context["category"]["column"] == (
        "CategoryName"
    )


def test_task_filter_context() -> None:
    context = get_task_filter_context(
        build_test_task()
    )

    assert len(context) == 1
    assert context[0]["table"] == "Orders"
    assert context[0]["column"] == "ShipCountry"
    assert context[0]["value"] == "Germany"


def test_required_table_context() -> None:
    context = get_required_table_context(
        build_test_plan(),
        build_test_task(),
    )

    assert "Orders" in context
    assert "Order Details" in context
    assert "Products" in context
    assert "Categories" in context

    assert "OrderID" in context[
        "Orders"
    ]["columns"]


def test_build_sql_generation_context() -> None:
    context = build_sql_generation_context(
        intent=build_test_intent(),
        plan=build_test_plan(),
        task=build_test_task(),
    )

    assert context["database_dialect"] == (
        "sqlite"
    )

    assert "net_revenue" in context[
        "metric_definitions"
    ]

    assert "category" in context[
        "dimension_mappings"
    ]

    assert context["sort_direction"] == (
        "descending"
    )

    assert context["limit"] == 5
    assert len(context["required_joins"]) == 3