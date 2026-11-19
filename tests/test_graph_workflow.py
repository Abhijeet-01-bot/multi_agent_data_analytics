from graph.workflow import (
    build_analytics_workflow,
)


def test_workflow_compiles() -> None:
    workflow = build_analytics_workflow()

    assert workflow is not None


def test_workflow_contains_required_nodes() -> None:
    workflow = build_analytics_workflow()

    graph_structure = workflow.get_graph()

    node_names = set(
        graph_structure.nodes.keys()
    )

    expected_nodes = {
        "initialize_request",
        "intent",
        "clarification",
        "unsupported",
        "planning",
        "select_task",
        "sql",
        "validate_result",
        "analytics",
        "evidence",
        "analysis",
        "needs_more_evidence",
        "reporting",
        "failure",
    }

    assert expected_nodes.issubset(
        node_names
    )