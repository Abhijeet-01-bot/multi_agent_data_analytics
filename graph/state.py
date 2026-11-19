from __future__ import annotations

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict


class AnalyticsWorkflowState(
    TypedDict,
    total=False,
):
    """
    Shared state for one analytical workflow run.

    Most fields use last-write-wins behavior.

    trace, warnings and errors use reducers so each node
    can append new values without removing earlier values.
    """

    # Request information
    request_id: str
    user_question: str

    # Workflow tracking
    status: str
    current_node: str

    # Agent outputs
    intent: dict[str, Any] | None
    plan: dict[str, Any] | None
    selected_task: dict[str, Any] | None

    sql_task_result: dict[str, Any] | None
    result_validation: dict[str, Any] | None
    analytics_result: dict[str, Any] | None
    evidence_bundle: dict[str, Any] | None
    analysis_result: dict[str, Any] | None
    final_report: dict[str, Any] | None

    capability_assessment: (
    dict[str, Any] | None
)

    # Decision fields
    clarification_required: bool
    clarification_question: str | None

    unsupported_request: bool
    unsupported_reason: str | None

    evidence_sufficient: bool

    # Future bounded replanning
    replan_count: int
    max_replans: int

    # Accumulated workflow diagnostics
    errors: Annotated[
        list[str],
        operator.add,
    ]

    warnings: Annotated[
        list[str],
        operator.add,
    ]

    trace: Annotated[
        list[str],
        operator.add,
    ]

    support_status: str | None
    user_message: str | None
    suggested_questions: list[str]