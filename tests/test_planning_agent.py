from typing import Any

import pytest

from agents.planning_agent import PlanningAgent
from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
    SortDirection,
)
from schemas.planning_schemas import (
    AnalyticalTask,
    ChartRecommendation,
    ChartType,
    ExecutionPlan,
    RequiredJoin,
    TaskType,
)


class FakeStructuredPlanningModel:
    """
    Predictable replacement for Gemini during tests.
    """

    def __init__(
        self,
        response: ExecutionPlan | dict[str, Any],
    ) -> None:
        self.response = response
        self.received_input: object | None = None

    def invoke(
        self,
        input: object,
    ) -> ExecutionPlan | dict[str, Any]:
        self.received_input = input
        return self.response

def disable_generic_planning(
    monkeypatch,
) -> None:
    """
    Force PlanningAgent tests through the legacy
    LLM-planning path.
    """

    def compiler_disabled(
        intent,
    ):
        raise ValueError(
            "Generic planning disabled for test."
        )

    monkeypatch.setattr(
        PlanningAgent,
        "_build_query_spec_plan",
        staticmethod(
            compiler_disabled
        ),
    )

    monkeypatch.setattr(
        PlanningAgent,
        "_build_deterministic_plan",
        staticmethod(
            lambda intent: None
        ),
    )
def build_valid_intent() -> IntentResult:
    return IntentResult(
        business_objective=(
            "Identify the top five categories by "
            "net revenue in Germany."
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


def build_valid_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_summary=(
            "Calculate category-level net revenue for "
            "Germany and rank the top five."
        ),
        tasks=[
            AnalyticalTask(
                task_id="T1",
                description=(
                    "Calculate net revenue by category "
                    "for orders shipped to Germany."
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
                depends_on=[],
            ),
            AnalyticalTask(
                task_id="T2",
                description=(
                    "Rank the category results in "
                    "descending order and return five."
                ),
                task_type=TaskType.RANKING,
                metrics=["net_revenue"],
                dimensions=["category"],
                required_tables=[],
                expected_columns=[
                    "CategoryName",
                    "NetRevenue",
                    "RevenueRank",
                ],
                depends_on=["T1"],
            ),
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
                reason=(
                    "Connect shipping geography to "
                    "line-item revenue."
                ),
            ),
            RequiredJoin(
                left_table="Order Details",
                left_column="ProductID",
                right_table="Products",
                right_column="ProductID",
                reason=(
                    "Connect line-item revenue to "
                    "products."
                ),
            ),
            RequiredJoin(
                left_table="Products",
                left_column="CategoryID",
                right_table="Categories",
                right_column="CategoryID",
                reason=(
                    "Connect products to category names."
                ),
            ),
        ],
        chart_recommendations=[
            ChartRecommendation(
                chart_type=ChartType.HORIZONTAL_BAR,
                title=(
                    "Top Categories by Net Revenue "
                    "in Germany"
                ),
                x_field="NetRevenue",
                y_field="CategoryName",
                reason=(
                    "A horizontal bar chart clearly "
                    "shows ranked category values."
                ),
            )
        ],
        completion_criteria=[
            (
                "The output contains no more than "
                "five categories."
            ),
            (
                "Categories are ordered by net "
                "revenue descending."
            ),
            (
                "Only Germany shipping records "
                "are included."
            ),
        ],
        confidence=0.98,
    )


def test_planning_agent_creates_plan(
    monkeypatch,
) -> None:
    disable_generic_planning(
        monkeypatch
    )

    fake_model = (
        FakeStructuredPlanningModel(
            build_valid_plan()
        )
    )

    agent = PlanningAgent(
        structured_model=fake_model
    )

    result = agent.create_plan(
        build_valid_intent()
    )

    assert isinstance(
        result,
        ExecutionPlan,
    )

    assert len(result.tasks) == 2

def test_planning_agent_validates_dictionary(
    monkeypatch,
) -> None:
    disable_generic_planning(
        monkeypatch
    )

    dictionary_plan = (
        build_valid_plan().model_dump(
            mode="json"
        )
    )

    agent = PlanningAgent(
        structured_model=(
            FakeStructuredPlanningModel(
                dictionary_plan
            )
        )
    )

    result = agent.create_plan(
        build_valid_intent()
    )

    assert isinstance(
        result,
        ExecutionPlan,
    )

    assert (
        result.tasks[0].task_type
        == TaskType.DATA_RETRIEVAL
    )


def test_clarification_intent_is_rejected() -> None:
    intent = IntentResult(
        business_objective=(
            "Understand declining performance."
        ),
        metrics=[],
        dimensions=[],
        analysis_types=[
            AnalysisType.ROOT_CAUSE
        ],
        ambiguity_reasons=[
            "Performance is ambiguous."
        ],
        clarification_required=True,
        clarification_question=(
            "Which metric should I analyze?"
        ),
        confidence=0.8,
    )

    fake_model = FakeStructuredPlanningModel(
        build_valid_plan()
    )

    agent = PlanningAgent(
        structured_model=fake_model
    )

    with pytest.raises(
        ValueError,
        match="requires clarification",
    ):
        agent.create_plan(intent)

    assert fake_model.received_input is None


def test_unsupported_intent_is_rejected() -> None:
    intent = IntentResult(
        business_objective=(
            "Predict tomorrow's stock market."
        ),
        metrics=[],
        dimensions=[],
        analysis_types=[],
        unsupported_request=True,
        unsupported_reason=(
            "Stock-market data is unavailable."
        ),
        confidence=1.0,
    )

    fake_model = FakeStructuredPlanningModel(
        build_valid_plan()
    )

    agent = PlanningAgent(
        structured_model=fake_model
    )

    with pytest.raises(
        ValueError,
        match="unsupported",
    ):
        agent.create_plan(intent)

    assert fake_model.received_input is None


def test_intent_without_metric_is_rejected() -> None:
    intent = IntentResult(
        business_objective=(
            "Show categories."
        ),
        metrics=[],
        dimensions=["category"],
        analysis_types=[],
        confidence=0.7,
    )

    agent = PlanningAgent(
        structured_model=(
            FakeStructuredPlanningModel(
                build_valid_plan()
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="without at least one approved metric",
    ):
        agent.create_plan(intent)


def test_execution_plan_rejects_unknown_dependency() -> None:
    with pytest.raises(
        ValueError,
        match="unknown task",
    ):
        ExecutionPlan(
            plan_summary="Invalid plan.",
            tasks=[
                AnalyticalTask(
                    task_id="T1",
                    description="Test task.",
                    task_type=(
                        TaskType.DATA_RETRIEVAL
                    ),
                    depends_on=["T99"],
                )
            ],
        )


def test_execution_plan_rejects_duplicate_task_ids() -> None:
    with pytest.raises(
        ValueError,
        match="unique task_id",
    ):
        ExecutionPlan(
            plan_summary="Invalid plan.",
            tasks=[
                AnalyticalTask(
                    task_id="T1",
                    description="First task.",
                    task_type=(
                        TaskType.DATA_RETRIEVAL
                    ),
                ),
                AnalyticalTask(
                    task_id="T1",
                    description="Second task.",
                    task_type=TaskType.RANKING,
                ),
            ],
        )
def test_filtered_revenue_uses_deterministic_plan() -> None:
    intent = IntentResult(
        business_objective=(
            "Calculate net revenue for orders "
            "shipped to XYZ_NONEXISTENT."
        ),
        metrics=[
            "net_revenue"
        ],
        dimensions=[],
        filters=[
            IntentFilter(
                field="ship_country",
                operator="equals",
                value=(
                    "XYZ_NONEXISTENT"
                ),
            )
        ],
        analysis_types=[
            AnalysisType.AGGREGATION
        ],
        confidence=1.0,
    )

    plan = (
        PlanningAgent
        ._build_deterministic_plan(
            intent
        )
    )

    assert plan is not None
    assert len(plan.tasks) == 1

    task = plan.tasks[0]

    assert task.task_id == "T1"

    assert task.metrics == [
        "net_revenue"
    ]

    assert task.dimensions == []

    assert task.required_tables == [
        "Orders",
        "Order Details",
    ]

    assert task.expected_columns == [
        "NetRevenue"
    ]

    assert len(
        plan.required_joins
    ) == 1

    assert (
        plan.required_joins[
            0
        ].left_table
        == "Orders"
    )

    assert (
        plan.required_joins[
            0
        ].right_table
        == "Order Details"
    )
def test_llm_plan_over_safe_limit_is_rejected(
    monkeypatch,
) -> None:
    disable_generic_planning(
        monkeypatch
    )

    excessive_plan = (
        build_valid_plan().model_dump(
            mode="json"
        )
    )

    base_task = excessive_plan[
        "tasks"
    ][0]

    excessive_plan["tasks"] = []

    for index in range(
        1,
        12,
    ):
        task = dict(base_task)
        task["task_id"] = f"T{index}"

        # Avoid invalid dependency references in the
        # generated fixture.
        task["depends_on"] = []

        excessive_plan[
            "tasks"
        ].append(task)

    agent = PlanningAgent(
        structured_model=(
            FakeStructuredPlanningModel(
                excessive_plan
            )
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "exceeding the safe limit"
        ),
    ):
        agent.create_plan(
            build_valid_intent()
        )

def test_query_spec_planning_creates_single_task() -> None:
    agent = PlanningAgent(
        structured_model=(
            FakeStructuredPlanningModel(
                build_valid_plan()
            )
        )
    )

    result = agent.create_plan(
        build_valid_intent()
    )

    assert len(result.tasks) == 1

    task = result.tasks[0]

    assert task.task_id == "T1"

    assert task.task_type == (
        TaskType.RANKING
    )

    assert task.metrics == [
        "net_revenue"
    ]

    assert task.dimensions == [
        "category"
    ]

    assert task.expected_columns == [
        "CategoryName",
        "NetRevenue",
    ]