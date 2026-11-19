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
    def build_plan_from_query_spec(
        query_spec,
    ) -> ExecutionPlan:
        def column_name(value) -> str:
            if hasattr(value, "value"):
                return str(value.value)
            return str(value)

        expected_columns = [
            column_name(dimension)
            for dimension in query_spec.dimensions
        ]
        expected_columns.append(
            column_name(query_spec.metric)
        )

        task_type = TaskType.AGGREGATION
        operation_names = {
            column_name(operation).lower()
            for operation in query_spec.operations
        }

        if "rank" in operation_names:
            task_type = TaskType.RANKING
        elif "trend" in operation_names:
            task_type = TaskType.TREND_ANALYSIS

        return ExecutionPlan(
            plan_summary=(
                "Compile and execute the normalized "
                "analytical query specification."
            ),
            tasks=[
                AnalyticalTask(
                    task_id="T1",
                    description=(
                        "Execute the requested metric, "
                        "dimensions and filters."
                    ),
                    task_type=task_type,
                    metrics=[
                        query_spec.metric
                    ],
                    dimensions=(
                        query_spec.dimensions
                    ),
                    filters=[
                        query_filter.model_dump(
                            mode="json"
                        )
                        for query_filter
                        in query_spec.filters
                    ],
                    required_tables=[],
                    expected_columns=(
                        expected_columns
                    ),
                )
            ],
            confidence=1.0,
        )

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