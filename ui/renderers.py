from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from schemas.evidence_schemas import (
    EvidenceBundle,
)
from schemas.visualization_schemas import (
    VisualizationSpec,
)
from tools.visualization_tool import (
    create_plotly_figure,
)
from tools.visualization_validator import (
    validate_visualization_spec,
)


STATUS_LABELS = {
    "completed": "Analysis completed",
    "running": "Analysis running",
    "needs_clarification": (
        "Clarification required"
    ),
    "unsupported": "Unsupported request",
    "unsupported_analysis": (
        "Analysis type not supported"
    ),
    "unsupported_data": (
        "Required data is unavailable"
    ),
    "needs_more_evidence": (
        "Additional evidence required"
    ),
    "no_data": "No matching data found",
    "failed": "Analysis failed",
}
STATUS_LABELS.update(
    {
        "unsupported_analysis": (
            "Analysis type not yet supported"
        ),
        "unsupported_data": (
            "Required data is unavailable"
        ),
        "no_data": (
            "No matching data was found"
        ),
    }
)


def get_status_label(
    status: str | None,
) -> str:
    return STATUS_LABELS.get(
        status or "",
        "Unknown status",
    )


def get_query_rows(
    workflow_result: dict[str, Any],
) -> list[dict[str, Any]]:
    sql_result = workflow_result.get(
        "sql_task_result"
    ) or {}

    execution = sql_result.get(
        "execution"
    ) or {}

    rows = execution.get(
        "rows",
        [],
    )

    return (
        rows
        if isinstance(rows, list)
        else []
    )


def get_generated_sql(
    workflow_result: dict[str, Any],
) -> str | None:
    sql_result = workflow_result.get(
        "sql_task_result"
    ) or {}

    query = sql_result.get(
        "query"
    ) or {}

    sql = query.get("sql")

    return (
        str(sql)
        if sql
        else None
    )


def get_sql_parameters(
    workflow_result: dict[str, Any],
) -> dict[str, Any]:
    sql_result = workflow_result.get(
        "sql_task_result"
    ) or {}

    query = sql_result.get(
        "query"
    ) or {}

    parameters = query.get(
        "parameters",
        {},
    )

    return (
        parameters
        if isinstance(parameters, dict)
        else {}
    )


def render_status(
    workflow_result: dict[str, Any],
) -> None:
    status = workflow_result.get(
        "status",
        "unknown",
    )

    label = get_status_label(status)

    if status == "completed":
        st.success(label)

    elif status == "needs_clarification":
        st.warning(label)

    elif status == "unsupported":
        st.info(label)

    elif status == "needs_more_evidence":
        st.warning(label)

    elif status == "failed":
        st.error(label)

    elif status == "no_data":
        st.info(label)

    else:
        st.info(label)


def render_clarification(
    workflow_result: dict[str, Any],
) -> None:
    if not workflow_result.get(
        "clarification_required",
        False,
    ):
        return

    question = workflow_result.get(
        "clarification_question"
    )

    st.warning(
        question
        or (
            "The request requires clarification "
            "before analysis can continue."
        )
    )


def render_unsupported(
    workflow_result: dict[str, Any],
) -> None:
    if not workflow_result.get(
        "unsupported_request",
        False,
    ):
        return

    reason = workflow_result.get(
        "unsupported_reason"
    )

    st.info(
        reason
        or (
            "The connected Northwind data cannot "
            "answer this request."
        )
    )


def render_executive_report(
    report: dict[str, Any],
) -> None:
    st.header(
        report.get(
            "report_title",
            "Analysis Report",
        )
    )

    st.subheader("Executive summary")

    st.write(
        report.get(
            "executive_summary",
            "No executive summary was generated.",
        )
    )

    findings = report.get(
        "findings",
        [],
    )

    if findings:
        st.subheader("Key findings")

        for finding in findings:
            title = finding.get(
                "title",
                "Finding",
            )

            explanation = finding.get(
                "explanation",
                "",
            )

            importance = finding.get(
                "importance",
                "medium",
            )

            with st.container(
                border=True
            ):
                st.markdown(
                    f"**{title}**"
                )

                st.caption(
                    f"Importance: {importance}"
                )

                st.write(explanation)

    recommendations = report.get(
        "recommendations",
        [],
    )

    if recommendations:
        st.subheader("Recommendations")

        for recommendation in recommendations:
            action = recommendation.get(
                "action",
                "Recommendation",
            )

            rationale = recommendation.get(
                "rationale",
                "",
            )

            priority = recommendation.get(
                "priority",
                "medium",
            )

            with st.container(
                border=True
            ):
                st.markdown(
                    f"**{action}**"
                )

                st.caption(
                    f"Priority: {priority}"
                )

                st.write(rationale)

                limitation = (
                    recommendation.get(
                        "limitation"
                    )
                )

                if limitation:
                    st.caption(
                        f"Limitation: {limitation}"
                    )

    limitations = report.get(
        "limitations",
        [],
    )

    if limitations:
        st.subheader("Limitations")

        for limitation in limitations:
            st.markdown(
                f"- {limitation}"
            )

    methodology = report.get(
        "methodology_summary"
    )

    if methodology:
        with st.expander(
            "Methodology"
        ):
            st.write(methodology)


def render_visualizations(
    workflow_result: dict[str, Any],
) -> None:
    report = workflow_result.get(
        "final_report"
    ) or {}

    visualization_data = report.get(
        "visualizations",
        [],
    )

    evidence_data = workflow_result.get(
        "evidence_bundle"
    )

    if (
        not visualization_data
        or not evidence_data
    ):
        return

    try:
        evidence_bundle = (
            EvidenceBundle.model_validate(
                evidence_data
            )
        )

    except Exception as error:
        st.warning(
            "Visualizations could not be loaded: "
            f"{error}"
        )
        return

    st.subheader("Visualizations")

    for visualization_item in (
        visualization_data
    ):
        try:
            specification = (
                VisualizationSpec.model_validate(
                    visualization_item
                )
            )

            validation = (
                validate_visualization_spec(
                    spec=specification,
                    evidence_bundle=(
                        evidence_bundle
                    ),
                )
            )

            if not validation.is_valid:
                st.warning(
                    (
                        f"Chart "
                        f"{specification.visualization_id} "
                        "was skipped: "
                        + "; ".join(
                            validation.errors
                        )
                    )
                )
                continue

            figure = create_plotly_figure(
                spec=specification,
                evidence_bundle=(
                    evidence_bundle
                ),
            )

            st.plotly_chart(
                figure,
                width="stretch",
                key=(
                    "chart_"
                    f"{specification.visualization_id}"
                ),
            )

            if specification.description:
                st.caption(
                    specification.description
                )

        except Exception as error:
            st.warning(
                "A chart could not be rendered: "
                f"{error}"
            )


def render_query_result(
    workflow_result: dict[str, Any],
) -> None:
    rows = get_query_rows(
        workflow_result
    )

    if not rows:
        return

    st.subheader("Query result")

    dataframe = pd.DataFrame(rows)

    st.dataframe(
        dataframe,
        width="stretch",
        hide_index=True,
    )


def render_technical_details(
    workflow_result: dict[str, Any],
) -> None:
    with st.expander(
        "Technical details",
        expanded=False,
    ):
        tabs = st.tabs(
            [
                "Workflow trace",
                "Intent",
                "Plan",
                "SQL",
                "Evidence",
                "Analysis",
                "Raw state",
            ]
        )

        with tabs[0]:
            for item in workflow_result.get("trace", []):
                st.markdown(f"- {item}")

        with tabs[1]:
            st.json(workflow_result.get("intent") or {})

        with tabs[2]:
            st.json(workflow_result.get("plan") or {})

        with tabs[3]:
            sql = get_generated_sql(workflow_result)

            if sql:
                st.code(sql, language="sql")

            parameters = get_sql_parameters(workflow_result)

            if parameters:
                st.markdown("**Parameters**")
                st.json(parameters)

        with tabs[4]:
            st.json(workflow_result.get("evidence_bundle") or {})

        with tabs[5]:
            st.json(workflow_result.get("analysis_result") or {})

        with tabs[6]:
            st.json(workflow_result)


def render_errors_and_warnings(
    workflow_result: dict[str, Any],
) -> None:
    errors = workflow_result.get(
        "errors",
        [],
    )

    warnings = workflow_result.get(
        "warnings",
        [],
    )

    if errors:
        with st.expander(
            "Errors",
            expanded=True,
        ):
            for error in errors:
                st.error(error)

    if warnings:
        with st.expander(
            "Warnings",
            expanded=False,
        ):
            for warning in warnings:
                st.warning(warning)

def render_user_message(
    workflow_result: dict[str, Any],
) -> None:
    message = workflow_result.get(
        "user_message"
    )

    if message:
        st.info(message)

    suggestions = workflow_result.get(
        "suggested_questions",
        [],
    )

    if suggestions:
        st.markdown(
            "**Try one of these questions:**"
        )

        for suggestion in suggestions:
            st.markdown(
                f"- {suggestion}"
            )