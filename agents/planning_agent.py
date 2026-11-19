from __future__ import annotations

from typing import Protocol

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from config.llm import create_llm
from prompts.planning_prompt import (
    PLANNING_SYSTEM_PROMPT,
    build_planning_user_prompt,
)
from schemas.intent_schemas import IntentResult
from schemas.planning_schemas import ExecutionPlan
from tools.planning_context import (
    build_planning_context,
)
from schemas.intent_schemas import (
    IntentResult,
)
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
    RequiredJoin,
    TaskType,
)


class StructuredPlanningModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> ExecutionPlan:
        ...


class PlanningAgent:
    """
    Convert a validated intent into an ordered analytical
    execution plan.
    """

    def __init__(
        self,
        structured_model: (
            StructuredPlanningModel | None
        ) = None,
    ) -> None:
        if structured_model is None:
            llm = create_llm()

            structured_model = (
                llm.with_structured_output(
                    ExecutionPlan,
                    method="json_schema",
                )
            )

        self.structured_model = structured_model

    @staticmethod
    def _build_deterministic_plan(
        intent: IntentResult,
    ) -> ExecutionPlan | None:
        metrics = set(intent.metrics)

        dimensions = set(
            intent.dimensions
    )

        filters = {
            intent_filter.field: (
            intent_filter.value
        )
        for intent_filter
        in intent.filters
    }

    # -----------------------------
    # Total Order Count
    # -----------------------------
        if (
            metrics == {"order_count"}
            and not dimensions
            and not filters
        ):
            task = AnalyticalTask(
                task_id="T1",
                description=(
                "Count unique orders."
            ),
                task_type=(
                TaskType.AGGREGATION
            ),
                metrics=[
                "order_count"
            ],
                dimensions=[],
                filters=[],
                required_tables=[
                "Orders"
            ],
                expected_columns=[
                "OrderCount"
            ],
            )

            return ExecutionPlan(
            plan_summary=(
                "Calculate total order count."
            ),
            tasks=[task],
            required_tables=[
                "Orders"
            ],
            required_joins=[],
            confidence=1.0,
            )

    # -----------------------------
    # Total Net Revenue
    # -----------------------------
        if (
            metrics == {"net_revenue"}
            and not dimensions
            and not filters
        ):
            task = AnalyticalTask(
                task_id="T1",
                description=(
                "Calculate total net revenue."
            ),
                task_type=(
                TaskType.AGGREGATION
            ),
                metrics=[
                "net_revenue"
            ],
                dimensions=[],
                filters=[],
                required_tables=[
                "Order Details"
            ],
                expected_columns=[
                "NetRevenue"
            ],
            )

            return ExecutionPlan(
            plan_summary=(
                "Calculate total net revenue."
            ),
            tasks=[task],
            required_tables=[
                "Order Details"
            ],
            required_joins=[],
            confidence=1.0,
            )

    # -----------------------------
    # Filtered Revenue
    # -----------------------------
        if (
            metrics == {"net_revenue"}
            and not dimensions
            and set(filters.keys())
            == {"ship_country"}
        ):
            country = filters[
            "ship_country"
            ]

            task = AnalyticalTask(
                task_id="T1",
                description=(
                "Calculate total net revenue "
                f"for orders shipped to "
                f"{country}."
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
                    "field": (
                        "ship_country"
                    ),
                    "operator": (
                        "equals"
                    ),
                    "value": country,
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

            return ExecutionPlan(
            plan_summary=(
                "Calculate country-level "
                "filtered net revenue."
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

    # -----------------------------
    # Top Categories By Revenue
    # -----------------------------
        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and not filters
        ):
            safe_limit = max(
                1,
                min(
                    int(
                        intent.limit or 5
                    ),
                    100,
                ),
            )

            task = AnalyticalTask(
                task_id="T1",
                description=(
                "Calculate category net "
                "revenue ranking."
            ),
                task_type=(
                TaskType.RANKING
            ),
                metrics=[
                "net_revenue"
            ],
                dimensions=[
                "category"
            ],
                filters=[],
                required_tables=[
                "Order Details",
                "Products",
                "Categories",
            ],
                expected_columns=[
                "CategoryName",
                "NetRevenue",
            ],
            )

            return ExecutionPlan(
            plan_summary=(
                "Rank categories by "
                "net revenue."
            ),
            tasks=[task],
            required_tables=[
                "Order Details",
                "Products",
                "Categories",
            ],
            required_joins=[
                RequiredJoin(
                    left_table=(
                        "Order Details"
                    ),
                    left_column=(
                        "ProductID"
                    ),
                    right_table=(
                        "Products"
                    ),
                    right_column=(
                        "ProductID"
                    ),
                ),
                RequiredJoin(
                    left_table="Products",
                    left_column=(
                        "CategoryID"
                    ),
                    right_table=(
                        "Categories"
                    ),
                    right_column=(
                        "CategoryID"
                    ),
                ),
            ],
            confidence=1.0,
            )

    # -----------------------------
    # Top Categories By Revenue
    # In Country
    # -----------------------------
        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and "ship_country"
            in filters
        ):
            country = filters[
            "ship_country"
            ]

            task = AnalyticalTask(
                task_id="T1",
                description=(
                "Calculate category "
                "revenue in "
                f"{country}."
                ),
                task_type=(
                TaskType.RANKING
                ),
                metrics=[
                "net_revenue"
                ],
                dimensions=[
                "category"
                ],
                filters=[
                {
                    "field": (
                        "ship_country"
                    ),
                    "operator": (
                        "equals"
                    ),
                    "value": country,
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

            return ExecutionPlan(
            plan_summary=(
                "Category revenue "
                "ranking by country."
            ),
            tasks=[task],
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
                    right_table=(
                        "Order Details"
                    ),
                    right_column="OrderID",
                ),
                RequiredJoin(
                    left_table=(
                        "Order Details"
                    ),
                    left_column=(
                        "ProductID"
                    ),
                    right_table="Products",
                    right_column=(
                        "ProductID"
                    ),
                ),
                RequiredJoin(
                    left_table="Products",
                    left_column=(
                        "CategoryID"
                    ),
                    right_table=(
                        "Categories"
                    ),
                    right_column=(
                        "CategoryID"
                    ),

                ),
            ],
            confidence=1.0,
            )

        return None
    def create_plan(
        self,
        intent: IntentResult,
    ) -> ExecutionPlan:
        if intent.clarification_required:
            raise ValueError(
        "The intent requires clarification before "
        "a plan can be created."
    )

        if intent.unsupported_request:
            raise ValueError(
                "A plan cannot be created for an "
                "unsupported request."
            )

        if not intent.metrics:
            raise ValueError(
                "A plan cannot be created without "
                "at least one approved metric."
            )

        # Common supported patterns do not use Ollama.
        deterministic_plan = (
            self._build_deterministic_plan(
                intent
            )
        )

        if deterministic_plan is not None:
            return deterministic_plan

        # Existing LLM planning path starts here.
        planning_context = (
            build_planning_context(
                intent
            )
        )

        user_prompt = build_planning_user_prompt(
            intent=intent,
            planning_context=(
                planning_context
            ),
        )

        messages = [
            SystemMessage(
                content=PLANNING_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]

        raw_result = self.structured_model.invoke(
            messages
        )

        if isinstance(
            raw_result,
            ExecutionPlan,
        ):
            result = raw_result

        elif isinstance(
            raw_result,
            dict,
        ):
            # Remove empty task objects produced by small
            # local models before Pydantic validation.
            normalized_result = dict(
                raw_result
            )

            raw_tasks = normalized_result.get(
                "tasks",
                [],
            )

            if isinstance(raw_tasks, list):
                normalized_result["tasks"] = [
                    task
                    for task in raw_tasks
                    if (
                        isinstance(task, dict)
                        and task.get("task_id")
                        and task.get("description")
                        and task.get("task_type")
                    )
                ]

            result = ExecutionPlan.model_validate(
                normalized_result
            )

        elif hasattr(
            raw_result,
            "model_dump",
        ):
            normalized_result = (
                raw_result.model_dump(
                    mode="json"
                )
            )

            result = ExecutionPlan.model_validate(
                normalized_result
            )

        else:
            raise TypeError(
                "The Planning Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        # Add the plan-size guard HERE, after Pydantic
        # validation and before returning the result.
        maximum_plan_tasks = 10

        if len(result.tasks) > maximum_plan_tasks:
            raise ValueError(
                "The generated plan contains "
                f"{len(result.tasks)} tasks, exceeding "
                f"the safe limit of "
                f"{maximum_plan_tasks}. Please simplify "
                "the question or use a supported "
                "analytical pattern."
            )

        return result