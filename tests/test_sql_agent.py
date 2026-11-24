from typing import Any

from agents.sql_agent import SQLGenerationAgent
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
from schemas.sql_generation_schemas import (
    GeneratedSQLQuery,
)
from semantic.query_spec_builder import build_query_spec

class SequenceSQLModel:
    """
    Fake structured model that returns responses in order.
    """

    def __init__(
        self,
        responses: list[
            GeneratedSQLQuery | dict[str, Any]
        ],
    ) -> None:
        self.responses = responses
        self.call_count = 0
        self.received_inputs: list[object] = []

    def invoke(
        self,
        input: object,
    ) -> GeneratedSQLQuery | dict[str, Any]:
        self.received_inputs.append(input)

        response = self.responses[
            self.call_count
        ]

        self.call_count += 1

        return response

def disable_compiled_and_deterministic_sql(
    monkeypatch,
) -> None:
    """
    Force SQLGenerationAgent tests through the
    legacy LLM generation and retry path.
    """

    def query_spec_disabled(
        intent,
    ):
        raise ValueError(
            "QuerySpec compiler disabled for test."
        )

    monkeypatch.setattr(
        "agents.sql_agent.build_query_spec",
        query_spec_disabled,
    )

    monkeypatch.setattr(
        SQLGenerationAgent,
        "_build_deterministic_query",
        staticmethod(
            lambda intent, task: None
        ),
    )

def build_intent() -> IntentResult:
    return IntentResult(
        business_objective=(
            "Rank categories by revenue in Germany."
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


def build_task() -> AnalyticalTask:
    return AnalyticalTask(
        task_id="T1",
        description=(
            "Calculate net revenue by category for "
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


def build_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_summary=(
            "Calculate and rank category revenue."
        ),
        tasks=[build_task()],
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


def build_valid_query() -> GeneratedSQLQuery:
    return GeneratedSQLQuery(
        task_id="T1",
        sql="""
            SELECT
                c.CategoryName AS CategoryName,
                ROUND(
                    SUM(
                        od.UnitPrice
                        * od.Quantity
                        * (1 - od.Discount)
                    ),
                    2
                ) AS NetRevenue
            FROM Orders AS o
            JOIN "Order Details" AS od
                ON o.OrderID = od.OrderID
            JOIN Products AS p
                ON od.ProductID = p.ProductID
            JOIN Categories AS c
                ON p.CategoryID = c.CategoryID
            WHERE o.ShipCountry = :ship_country
            GROUP BY
                c.CategoryID,
                c.CategoryName
            ORDER BY
                NetRevenue DESC
            LIMIT 5
        """,
        parameters={
            "ship_country": "Germany",
        },
        referenced_tables=[
            "Orders",
            "Order Details",
            "Products",
            "Categories",
        ],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
        explanation=(
            "Calculates discounted category revenue "
            "for orders shipped to Germany."
        ),
    )


def test_sql_agent_executes_valid_query(
    monkeypatch,
) -> None:
    disable_compiled_and_deterministic_sql(
        monkeypatch
    )

    model = SequenceSQLModel(
        [build_valid_query()]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.attempts == 1

    assert result.validation is not None
    assert result.validation.is_valid is True

    assert result.execution is not None
    assert result.execution.success is True

    assert "CategoryName" in (
        result.execution.columns
    )

    assert "NetRevenue" in (
        result.execution.columns
    )

    assert model.call_count == 1
def test_sql_agent_corrects_unknown_table(
    monkeypatch,
) -> None:
    disable_compiled_and_deterministic_sql(
        monkeypatch
    )

    invalid_query = GeneratedSQLQuery(
        task_id="T1",
        sql="""
            SELECT
                CategoryName,
                SUM(Revenue) AS NetRevenue
            FROM Sales
            GROUP BY CategoryName
        """,
        parameters={},
        referenced_tables=["Sales"],
        expected_columns=[
            "CategoryName",
            "NetRevenue",
        ],
        explanation="Invalid initial query.",
    )

    model = SequenceSQLModel(
        [
            invalid_query,
            build_valid_query(),
        ]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.attempts == 2
    assert len(
        result.correction_history
    ) == 1

    assert any(
        "Unknown table" in error
        for error
        in result.correction_history[
            0
        ].validation_errors
    )

    assert model.call_count == 2


def test_sql_agent_corrects_execution_error(
    monkeypatch,
) -> None:
    disable_compiled_and_deterministic_sql(
        monkeypatch
    )

    invalid_column_query = GeneratedSQLQuery(
        task_id="T1",
        sql="""
            SELECT
                SUM(SalesAmount) AS NetRevenue
            FROM Orders
        """,
        parameters={},
        referenced_tables=["Orders"],
        expected_columns=["NetRevenue"],
        explanation=(
            "Invalid query using a nonexistent column."
        ),
    )

    model = SequenceSQLModel(
        [
            invalid_column_query,
            build_valid_query(),
        ]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.attempts == 2
    assert len(
        result.correction_history
    ) == 1

    assert result.correction_history[
        0
    ].execution_errors

    assert model.call_count == 2


def test_dictionary_response_is_validated() -> None:
    dictionary_query = (
        build_valid_query().model_dump(
            mode="json"
        )
    )

    model = SequenceSQLModel(
        [dictionary_query]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert isinstance(
        result.query,
        GeneratedSQLQuery,
    )


def test_empty_generated_task_id_is_normalized() -> None:
    query_data = (
        build_valid_query().model_dump(
            mode="json"
        )
    )

    query_data["task_id"] = ""

    model = SequenceSQLModel(
        [query_data]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.query is not None
    assert result.query.task_id == "T1"

def test_empty_generated_task_id_is_normalized() -> None:
    query_data = (
        build_valid_query().model_dump(
            mode="json"
        )
    )

    query_data["task_id"] = ""

    model = SequenceSQLModel(
        [query_data]
    )

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.query is not None
    assert result.query.task_id == "T1"

def test_simple_order_count_uses_deterministic_sql() -> None:
    intent = IntentResult(
        business_objective=(
            "Count the total number of orders."
        ),
        metrics=["order_count"],
        dimensions=[],
        filters=[],
        analysis_types=[
            AnalysisType.AGGREGATION
        ],
        confidence=1.0,
    )

    task = AnalyticalTask(
        task_id="T1",
        description=(
            "Count unique orders."
        ),
        task_type=TaskType.AGGREGATION,
        metrics=["order_count"],
        dimensions=[],
        filters=[],
        required_tables=["Orders"],
        expected_columns=[
            "OrderCount"
        ],
    )

    plan = ExecutionPlan(
        plan_summary=(
            "Count all unique orders."
        ),
        tasks=[task],
        required_tables=["Orders"],
        confidence=1.0,
    )

    # No model response is needed because this task should
    # use deterministic SQL.
    model = SequenceSQLModel([])

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=intent,
        plan=plan,
        task=task,
    )

    assert result.success is True
    assert result.attempts == 1
    assert result.query is not None
    assert result.execution is not None

    assert model.call_count == 0

    assert (
    "COUNT(DISTINCT o.OrderID)"
    in result.query.sql
    )

    assert (
        "JOIN"
        not in result.query.sql.upper()
    )

    assert result.query.parameters == {}

    assert result.execution.columns == [
        "OrderCount"
    ]

    assert len(
        result.execution.rows
    ) == 1

def test_order_count_uses_expected_alias() -> None:
    intent = IntentResult(
        business_objective=(
            "Count the total number of orders."
        ),
        metrics=["order_count"],
        dimensions=[],
        filters=[],
        analysis_types=[
            AnalysisType.AGGREGATION
        ],
        confidence=1.0,
    )

    task = AnalyticalTask(
        task_id="T1",
        description="Count orders.",
        task_type=TaskType.AGGREGATION,
        metrics=["order_count"],
        dimensions=[],
        filters=[],
        required_tables=["Orders"],
        expected_columns=[
            "order_count"
        ],
    )

    query = (
        SQLGenerationAgent
        ._build_deterministic_query(
            intent=intent,
            task=task,
        )
    )

    assert query is not None

    assert (
        'AS "order_count"'
        in query.sql
    )

    assert query.expected_columns == [
        "order_count"
    ]
def test_category_revenue_ranking_uses_deterministic_sql() -> None:
    model = SequenceSQLModel([])

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=build_intent(),
        plan=build_plan(),
        task=build_task(),
    )

    assert result.success is True
    assert result.attempts == 1
    assert model.call_count == 0

    assert result.query is not None
    assert result.execution is not None

    sql = result.query.sql

    assert (
    'FROM "Order Details" AS od'
    in sql
    )
    assert "JOIN Products AS p" in sql
    assert "JOIN Categories AS c" in sql

    assert (
        "ON od.ProductID = p.ProductID"
        in sql
    )

    assert (
        "ON p.CategoryID = c.CategoryID"
        in sql
    )

    assert (
    "o.ShipCountry = :filter_0"
    in " ".join(
        sql.split()
    )
)
    assert result.query.parameters == {
    "filter_0": "Germany"
}


    assert "GROUP BY" in sql
    assert "ORDER BY" in sql
    assert "LIMIT 5" in sql

    

    assert result.execution.columns == [
        "CategoryName",
        "NetRevenue",
    ]

    assert (
        len(result.execution.rows)
        <= 5
    )
def test_filtered_revenue_with_no_matches_returns_empty() -> None:
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

    task = AnalyticalTask(
        task_id="T1",
        description=(
            "Calculate net revenue for orders "
            "shipped to XYZ_NONEXISTENT."
        ),
        task_type=(
            TaskType.AGGREGATION
        ),
        metrics=[
            "net_revenue"
        ],
        dimensions=[],
        filters=[
            {
                "field": "ship_country",
                "operator": "equals",
                "value": (
                    "XYZ_NONEXISTENT"
                ),
            }
        ],
        required_tables=[
            "Orders",
            "Order Details",
        ],
        expected_columns=[
            "NetRevenue"
        ],
    )

    plan = ExecutionPlan(
        plan_summary=(
            "Calculate filtered net revenue."
        ),
        tasks=[task],
        required_tables=[
            "Orders",
            "Order Details",
        ],
        required_joins=[
            RequiredJoin(
                left_table="Orders",
                left_column="OrderID",
                right_table=(
                    "Order Details"
                ),
                right_column="OrderID",
            )
        ],
        confidence=1.0,
    )

    model = SequenceSQLModel([])

    agent = SQLGenerationAgent(
        structured_model=model
    )

    result = agent.run_task(
        intent=intent,
        plan=plan,
        task=task,
    )

    assert result.success is True
    assert result.attempts == 1

    assert model.call_count == 0

    assert result.query is not None
    assert result.execution is not None

    assert result.query.parameters == {
    "filter_0": (
        "XYZ_NONEXISTENT"
    )
}

    assert (
        "HAVING COUNT(*) > 0"
        in result.query.sql
    )

    assert result.execution.rows == []

    assert (
        result.execution.returned_row_count
        == 0
    )