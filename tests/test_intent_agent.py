from typing import Any

from agents.intent_agent import (
    IntentUnderstandingAgent,
)
from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
    SortDirection,
)


class FakeStructuredIntentModel:
    """
    Predictable replacement for Gemini during tests.
    """

    def __init__(
        self,
        response: IntentResult | dict[str, Any],
    ) -> None:
        self.response = response
        self.received_input: object | None = None

    def invoke(
        self,
        input: object,
    ) -> IntentResult | dict[str, Any]:
        self.received_input = input
        return self.response


def test_intent_agent_extracts_ranking_intent() -> None:
    expected_response = IntentResult(
        business_objective=(
            "Rank categories by net revenue."
        ),
        metrics=["net_revenue"],
        dimensions=["category"],
        filters=[
            IntentFilter(
                field="customer_country",
                operator="equals",
                value="Germany",
            )
        ],
        analysis_types=[
            AnalysisType.RANKING
        ],
        sort_direction=SortDirection.DESCENDING,
        limit=5,
        clarification_required=False,
        confidence=0.96,
    )

    fake_model = FakeStructuredIntentModel(
        expected_response
    )

    agent = IntentUnderstandingAgent(
        structured_model=fake_model
    )

    result = agent.analyze(
        "Show the top five categories by "
        "revenue in Germany."
    )

    assert result.metrics == ["net_revenue"]
    assert result.dimensions == ["category"]
    assert result.limit == 5

    assert (
        result.sort_direction
        == SortDirection.DESCENDING
    )

    assert result.filters[0].field == (
        "customer_country"
    )

    assert result.filters[0].value == "Germany"
    assert result.clarification_required is False
    assert fake_model.received_input is not None


def test_intent_agent_returns_clarification() -> None:
    expected_response = IntentResult(
        business_objective=(
            "Understand a decline in performance."
        ),
        metrics=[],
        dimensions=[],
        analysis_types=[
            AnalysisType.ROOT_CAUSE
        ],
        ambiguity_reasons=[
            (
                "Performance does not identify "
                "a specific metric."
            )
        ],
        clarification_required=True,
        clarification_question=(
            "Which metric should I analyze: "
            "net revenue, order count, quantity, "
            "or average order value?"
        ),
        confidence=0.55,
    )

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                expected_response
            )
        )
    )

    result = agent.analyze(
        "Why did performance fall?"
    )

    assert result.clarification_required is True
    assert result.clarification_question
    assert result.metrics == []


def test_intent_agent_marks_unsupported_request() -> None:
    expected_response = IntentResult(
        business_objective=(
            "Predict tomorrow's stock market."
        ),
        metrics=[],
        dimensions=[],
        analysis_types=[],
        unsupported_request=True,
        unsupported_reason=(
            "The Northwind dataset contains order, "
            "customer and product data but no "
            "stock-market data."
        ),
        confidence=0.99,
    )

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                expected_response
            )
        )
    )

    result = agent.analyze(
        "Predict the stock market tomorrow."
    )

    assert result.unsupported_request is True
    assert result.unsupported_reason


def test_empty_question_does_not_call_model() -> None:
    expected_response = IntentResult(
        business_objective="Should not be used.",
        confidence=1.0,
    )

    fake_model = FakeStructuredIntentModel(
        expected_response
    )

    agent = IntentUnderstandingAgent(
        structured_model=fake_model
    )

    result = agent.analyze("   ")

    assert result.clarification_required is True
    assert result.clarification_question
    assert fake_model.received_input is None


def test_dictionary_response_is_validated() -> None:
    dictionary_response = {
        "business_objective": (
            "Calculate total order count."
        ),
        "metrics": ["order_count"],
        "dimensions": [],
        "filters": [],
        "analysis_types": ["aggregation"],
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.95,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                dictionary_response
            )
        )
    )

    result = agent.analyze(
        "How many orders are there?"
    )

    assert isinstance(result, IntentResult)
    assert result.metrics == ["order_count"]
    assert (
        AnalysisType.AGGREGATION
        in result.analysis_types
    )

def test_local_missing_order_metric_is_normalized() -> None:
    local_response = {
        "business_objective": (
            "Count all orders."
        ),
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "analysis_types": [],
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.8,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        "How many orders are there?"
    )

    assert result.metrics == [
        "order_count"
    ]

    assert (
        AnalysisType.AGGREGATION
        in result.analysis_types
    )

    assert (
        result.clarification_required
        is False
    )

def test_local_missing_revenue_metric_is_normalized() -> None:
    local_response = {
        "business_objective": (
            "Rank categories by revenue "
            "in Germany."
        ),
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "analysis_types": [],
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.8,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        (
            "Show the top five categories by "
            "revenue in Germany."
        )
    )

    assert result.metrics == [
        "net_revenue"
    ]

    assert "category" in result.dimensions

    assert result.limit == 5

    assert (
        result.sort_direction
        == SortDirection.DESCENDING
    )

    filter_fields = {
        intent_filter.field
        for intent_filter in result.filters
    }

    assert "ship_country" in filter_fields

def test_local_ambiguous_performance_requests_clarification() -> None:
    local_response = {
        "business_objective": (
            "Understand performance decline."
        ),
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "analysis_types": [],
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.5,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        "Why did performance fall?"
    )

    assert result.metrics == []

    assert (
        result.clarification_required
        is True
    )

    assert result.clarification_question

    assert (
        AnalysisType.ROOT_CAUSE
        in result.analysis_types
    )

def test_local_stock_market_request_is_unsupported() -> None:
    local_response = {
        "business_objective": (
            "Predict the stock market."
        ),
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "analysis_types": [],
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.5,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        "Predict the stock market tomorrow."
    )

    assert result.unsupported_request is True
    assert result.unsupported_reason
    assert result.metrics == []

def test_ambiguous_performance_overrides_guessed_metric() -> None:
    """
    The original wording is ambiguous, so an LLM-guessed
    metric must not be silently accepted.
    """

    local_response = {
        "business_objective": (
            "Understand the cause of a decline "
            "in performance."
        ),
        "metrics": [
            "net_revenue"
        ],
        "dimensions": [],
        "filters": [],
        "time_range": None,
        "analysis_types": [
            "root_cause"
        ],
        "sort_direction": None,
        "limit": None,
        "ambiguity_reasons": [],
        "clarification_required": False,
        "clarification_question": None,
        "unsupported_request": False,
        "unsupported_reason": None,
        "confidence": 0.9,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        "Why did performance fall?"
    )

    assert result.metrics == []

    assert (
        result.clarification_required
        is True
    )

    assert result.clarification_question

    assert any(
        "performance" in reason.lower()
        for reason
        in result.ambiguity_reasons
    )

    assert (
        AnalysisType.ROOT_CAUSE
        in result.analysis_types
    )

    assert (
        result.unsupported_request
        is False
    )

def test_unsupported_request_clears_irrelevant_fields() -> None:
    local_response = {
        "business_objective": (
            "Predict the stock market."
        ),
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "analysis_types": [
            "ranking"
        ],
        "sort_direction": "descending",
        "limit": 1,
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 0.5,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        "Predict the stock market tomorrow."
    )

    assert result.unsupported_request is True
    assert result.unsupported_reason

    assert result.metrics == []
    assert result.dimensions == []
    assert result.filters == []
    assert result.analysis_types == []
    assert result.sort_direction is None
    assert result.limit is None

def test_monthly_category_comparison_is_normalized() -> None:
    local_response = {
        "business_objective": "Compare",
        "metrics": [
            "net_revenue"
        ],
        "dimensions": [
            "category",
            "product",
            "order_month",
        ],
        "filters": [],
        "analysis_types": [
            "aggregation",
            "comparison",
            "trend",
        ],
        "sort_direction": "descending",
        "limit": 1,
        "clarification_required": False,
        "unsupported_request": False,
        "confidence": 1.0,
    }

    agent = IntentUnderstandingAgent(
        structured_model=(
            FakeStructuredIntentModel(
                local_response
            )
        )
    )

    result = agent.analyze(
        (
            "Compare monthly sales for "
            "Beverages and Dairy Products."
        )
    )

    assert set(
        result.dimensions
    ) == {
        "category",
        "order_month",
    }

    assert len(result.filters) == 1

    category_filter = (
        result.filters[0]
    )

    assert (
        category_filter.field
        == "category"
    )

    assert (
        category_filter.operator
        == "in"
    )

    assert category_filter.value == [
        "Beverages",
        "Dairy Products",
    ]

    assert (
        result.sort_direction
        is None
    )

    assert result.limit is None