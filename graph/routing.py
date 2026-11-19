from __future__ import annotations

from typing import Literal

from graph.state import (
    AnalyticsWorkflowState,
)


IntentRoute = Literal[
    "planning",
    "clarification",
    "unsupported",
    "failure",
]

SuccessRoute = Literal[
    "success",
    "failure",
]

SQLRoute = Literal[
    "validate_result",
    "failure",
]

ValidationRoute = Literal[
    "analytics",
    "no_data",
    "failure",
]

EvidenceRoute = Literal[
    "analysis",
    "failure",
]

AnalysisRoute = Literal[
    "reporting",
    "needs_more_evidence",
    "failure",
]

CapabilityRoute = Literal[
    "planning",
    "clarification",
    "unsupported_analysis",
    "unsupported_data",
    "failure",
]


def route_after_intent(
    state: AnalyticsWorkflowState,
) -> IntentRoute:
    if state.get("status") == "failed":
        return "failure"

    if state.get(
        "clarification_required",
        False,
    ):
        return "clarification"

    if state.get(
        "unsupported_request",
        False,
    ):
        return "unsupported"

    return "planning"


def route_after_planning(
    state: AnalyticsWorkflowState,
) -> SuccessRoute:
    if state.get("status") == "failed":
        return "failure"

    if not state.get("plan"):
        return "failure"

    return "success"


def route_after_task_selection(
    state: AnalyticsWorkflowState,
) -> SuccessRoute:
    if state.get("status") == "failed":
        return "failure"

    if not state.get("selected_task"):
        return "failure"

    return "success"


def route_after_sql(
    state: AnalyticsWorkflowState,
) -> SQLRoute:
    if state.get("status") == "failed":
        return "failure"

    sql_result = state.get(
        "sql_task_result"
    )

    if not sql_result:
        return "failure"

    if not sql_result.get(
        "success",
        False,
    ):
        return "failure"

    return "validate_result"


def route_after_result_validation(
    state: AnalyticsWorkflowState,
) -> ValidationRoute:
    if state.get("status") == "failed":
        return "failure"

    if state.get("status") == "no_data":
        return "no_data"

    validation = state.get(
        "result_validation"
    )

    if not validation:
        return "failure"

    if not validation.get(
        "is_valid",
        False,
    ):
        return "failure"

    return "analytics"

def route_after_analytics(
    state: AnalyticsWorkflowState,
) -> SuccessRoute:
    if state.get("status") == "failed":
        return "failure"

    return "success"


def route_after_evidence(
    state: AnalyticsWorkflowState,
) -> EvidenceRoute:
    if state.get("status") == "failed":
        return "failure"

    bundle = state.get(
        "evidence_bundle"
    )

    if not bundle:
        return "failure"

    if (
        bundle.get(
            "validated_record_count",
            0,
        )
        < 1
    ):
        return "failure"

    return "analysis"


def route_after_analysis(
    state: AnalyticsWorkflowState,
) -> AnalysisRoute:
    if state.get("status") == "failed":
        return "failure"

    analysis = state.get(
        "analysis_result"
    )

    if not analysis:
        return "failure"

    if analysis.get(
        "evidence_sufficient",
        False,
    ):
        return "reporting"

    current_replans = state.get(
        "replan_count",
        0,
    )

    maximum_replans = state.get(
        "max_replans",
        1,
    )

    if current_replans < maximum_replans:
        return "needs_more_evidence"

    return "failure"


def route_after_reporting(
    state: AnalyticsWorkflowState,
) -> SuccessRoute:
    if state.get("status") == "failed":
        return "failure"

    if not state.get("final_report"):
        return "failure"

    return "success"



def route_after_capability(
    state: AnalyticsWorkflowState,
) -> CapabilityRoute:
    if state.get("status") == "failed":
        return "failure"

    support_status = state.get(
        "support_status"
    )

    if support_status == "supported":
        return "planning"

    if (
        support_status
        == "needs_clarification"
    ):
        return "clarification"

    if (
        support_status
        == "unsupported_analysis"
    ):
        return "unsupported_analysis"

    if (
        support_status
        == "unsupported_data"
    ):
        return "unsupported_data"

    return "failure"