from graph.routing import (
    route_after_analysis,
    route_after_analytics,
    route_after_evidence,
    route_after_intent,
    route_after_planning,
    route_after_reporting,
    route_after_result_validation,
    route_after_sql,
    route_after_task_selection,
)


def test_intent_routes_to_planning() -> None:
    state = {
        "status": "running",
        "clarification_required": False,
        "unsupported_request": False,
    }

    assert (
        route_after_intent(state)
        == "planning"
    )


def test_intent_routes_to_clarification() -> None:
    state = {
        "status": "running",
        "clarification_required": True,
        "unsupported_request": False,
    }

    assert (
        route_after_intent(state)
        == "clarification"
    )


def test_intent_routes_to_unsupported() -> None:
    state = {
        "status": "running",
        "clarification_required": False,
        "unsupported_request": True,
    }

    assert (
        route_after_intent(state)
        == "unsupported"
    )


def test_failed_intent_routes_to_failure() -> None:
    state = {
        "status": "failed"
    }

    assert (
        route_after_intent(state)
        == "failure"
    )


def test_successful_plan_continues() -> None:
    state = {
        "status": "running",
        "plan": {
            "tasks": []
        },
    }

    assert (
        route_after_planning(state)
        == "success"
    )


def test_missing_plan_fails() -> None:
    state = {
        "status": "running",
        "plan": None,
    }

    assert (
        route_after_planning(state)
        == "failure"
    )


def test_task_selection_success() -> None:
    state = {
        "status": "running",
        "selected_task": {
            "task_id": "T1"
        },
    }

    assert (
        route_after_task_selection(state)
        == "success"
    )


def test_sql_success_route() -> None:
    state = {
        "status": "running",
        "sql_task_result": {
            "success": True
        },
    }

    assert (
        route_after_sql(state)
        == "validate_result"
    )


def test_sql_failure_route() -> None:
    state = {
        "status": "running",
        "sql_task_result": {
            "success": False
        },
    }

    assert (
        route_after_sql(state)
        == "failure"
    )


def test_valid_result_routes_to_analytics() -> None:
    state = {
        "status": "running",
        "result_validation": {
            "is_valid": True,
            "empty_result": False,
        },
    }

    assert (
        route_after_result_validation(
            state
        )
        == "analytics"
    )


def test_invalid_result_routes_to_failure() -> None:
    state = {
        "status": "running",
        "result_validation": {
            "is_valid": False
        },
    }

    assert (
        route_after_result_validation(
            state
        )
        == "failure"
    )


def test_analytics_success() -> None:
    state = {
        "status": "running"
    }

    assert (
        route_after_analytics(state)
        == "success"
    )


def test_evidence_routes_to_analysis() -> None:
    state = {
        "status": "running",
        "evidence_bundle": {
            "validated_record_count": 1
        },
    }

    assert (
        route_after_evidence(state)
        == "analysis"
    )


def test_analysis_routes_to_reporting() -> None:
    state = {
        "status": "running",
        "analysis_result": {
            "evidence_sufficient": True
        },
        "replan_count": 0,
        "max_replans": 1,
    }

    assert (
        route_after_analysis(state)
        == "reporting"
    )


def test_analysis_requests_more_evidence() -> None:
    state = {
        "status": "running",
        "analysis_result": {
            "evidence_sufficient": False
        },
        "replan_count": 0,
        "max_replans": 1,
    }

    assert (
        route_after_analysis(state)
        == "needs_more_evidence"
    )


def test_replan_limit_routes_to_failure() -> None:
    state = {
        "status": "running",
        "analysis_result": {
            "evidence_sufficient": False
        },
        "replan_count": 1,
        "max_replans": 1,
    }

    assert (
        route_after_analysis(state)
        == "failure"
    )


def test_completed_report_routes_to_end() -> None:
    state = {
        "status": "completed",
        "final_report": {
            "report_title": "Test"
        },
    }

    assert (
        route_after_reporting(state)
        == "success"
    )

def test_empty_result_routes_to_no_data() -> None:
    state = {
        "status": "no_data",
        "result_validation": {
            "is_valid": False,
            "empty_result": True,
        },
    }

    assert (
        route_after_result_validation(
            state
        )
        == "no_data"
    )

from graph.nodes import no_data_node


def test_no_data_node_preserves_message() -> None:
    state = {
        "status": "no_data",
        "user_message": (
            "No records matched Germany."
        ),
        "trace": [],
    }

    result = no_data_node(state)

    assert result["status"] == "no_data"

    assert result["user_message"] == (
        "No records matched Germany."
    )