from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from graph.nodes import (
    capability_node,
    unsupported_analysis_node,
    unsupported_data_node,
)
from graph.nodes import (
    analysis_node,
    analytics_node,
    clarification_node,
    evidence_node,
    failure_node,
    initialize_request_node,
    intent_node,
    needs_more_evidence_node,
    no_data_node,
    planning_node,
    reporting_node,
    select_task_node,
    sql_node,
    unsupported_node,
    validate_result_node,
)
from graph.nodes import (
    analysis_node,
    analytics_node,
    clarification_node,
    evidence_node,
    failure_node,
    initialize_request_node,
    intent_node,
    needs_more_evidence_node,
    planning_node,
    reporting_node,
    select_task_node,
    sql_node,
    unsupported_node,
    validate_result_node,
)
from graph.routing import (
    route_after_capability,
)
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
from graph.state import (
    AnalyticsWorkflowState,
)


def build_analytics_workflow():
    """
    Build the initial single-task analytics workflow.
    """

    builder = StateGraph(
        AnalyticsWorkflowState
    )

    builder.add_node(
        "initialize_request",
        initialize_request_node,
    )

    builder.add_node(
        "intent",
        intent_node,
    )

    builder.add_node(
        "clarification",
        clarification_node,
    )

    builder.add_node(
        "unsupported",
        unsupported_node,
    )

    builder.add_node(
        "planning",
        planning_node,
    )
    builder.add_node(
    "capability",
    capability_node,
)   
    builder.add_node(
    "no_data",
    no_data_node,
)

    builder.add_node(
    "unsupported_analysis",
    unsupported_analysis_node,
)

    builder.add_node(
    "unsupported_data",
    unsupported_data_node,
)
    builder.add_node(
        "select_task",
        select_task_node,
    )

    builder.add_node(
        "sql",
        sql_node,
    )

    builder.add_node(
        "validate_result",
        validate_result_node,
    )

    builder.add_node(
        "analytics",
        analytics_node,
    )

    builder.add_node(
        "evidence",
        evidence_node,
    )

    builder.add_node(
        "analysis",
        analysis_node,
    )

    builder.add_node(
        "needs_more_evidence",
        needs_more_evidence_node,
    )

    builder.add_node(
        "reporting",
        reporting_node,
    )

    builder.add_node(
        "failure",
        failure_node,
    )

    # Initial fixed sequence
    builder.add_edge(
        START,
        "initialize_request",
    )

    builder.add_edge(
        "initialize_request",
        "intent",
    )

    # Intent branching
    builder.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "planning": "capability",
            "clarification": "clarification",
            "unsupported": "unsupported",
            "failure": "failure",
        },
    )
    builder.add_conditional_edges(
    "capability",
    route_after_capability,
    {
        "planning": "planning",
        "clarification": (
            "clarification"
        ),
        "unsupported_analysis": (
            "unsupported_analysis"
        ),
        "unsupported_data": (
            "unsupported_data"
        ),
        "failure": "failure",
    },
)

    builder.add_edge(
    "unsupported_analysis",
    END,
)

    builder.add_edge(
    "unsupported_data",
    END,
)

    builder.add_edge(
        "clarification",
        END,
    )

    builder.add_edge(
        "unsupported",
        END,
    )

    # Planning success/failure
    builder.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "success": "select_task",
            "failure": "failure",
        },
    )

    # Task-selection success/failure
    builder.add_conditional_edges(
        "select_task",
        route_after_task_selection,
        {
            "success": "sql",
            "failure": "failure",
        },
    )

    # SQL success/failure
    builder.add_conditional_edges(
        "sql",
        route_after_sql,
        {
            "validate_result": (
                "validate_result"
            ),
            "failure": "failure",
        },
    )

    # Result-validation success/failure
    builder.add_conditional_edges(
    "validate_result",
    route_after_result_validation,
    {
        "analytics": "analytics",
        "no_data": "no_data",
        "failure": "failure",
    },
)

    # Analytics success/failure
    builder.add_conditional_edges(
        "analytics",
        route_after_analytics,
        {
            "success": "evidence",
            "failure": "failure",
        },
    )

    # Evidence success/failure
    builder.add_conditional_edges(
        "evidence",
        route_after_evidence,
        {
            "analysis": "analysis",
            "failure": "failure",
        },
    )

    # Analysis decision
    builder.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "reporting": "reporting",
            "needs_more_evidence": (
                "needs_more_evidence"
            ),
            "failure": "failure",
        },
    )

    builder.add_edge(
        "needs_more_evidence",
        END,
    )

    # Reporting success/failure
    builder.add_conditional_edges(
        "reporting",
        route_after_reporting,
        {
            "success": END,
            "failure": "failure",
        },
    )

    builder.add_edge(
        "failure",
        END,
    )
    builder.add_edge(
    "no_data",
    END,
)

    return builder.compile()
    


analytics_workflow = (
    build_analytics_workflow()
)