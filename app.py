from __future__ import annotations

import time
from typing import Any

import streamlit as st

from config.settings import settings
from graph.workflow import (
    analytics_workflow,
)
from ui.renderers import (
    render_user_message,
)
from ui.ollama_status import (
    check_configured_model,
    check_ollama_server,
    start_ollama_server,
)
from ui.renderers import (
    render_clarification,
    render_errors_and_warnings,
    render_executive_report,
    render_query_result,
    render_status,
    render_technical_details,
    render_unsupported,
    render_visualizations,
)
from ui.renderers import (
    render_user_message,
)


st.set_page_config(
    page_title=(
        "Multi-Agent Data Analytics"
    ),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def initialize_session_state() -> None:
    defaults: dict[str, Any] = {
        "workflow_result": None,
        "last_question": "",
        "workflow_running": False,
        "run_history": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def run_workflow(
    question: str,
) -> dict[str, Any]:
    initial_state = {
        "user_question": question,
        "errors": [],
        "warnings": [],
        "trace": [],
        "replan_count": 0,
        "max_replans": 1,
    }

    return analytics_workflow.invoke(
        initial_state,
        config={
            "recursion_limit": 30
        },
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.title("System status")

        provider = (
            settings.llm_provider.lower()
        )

        st.markdown(
            f"**LLM provider:** `{provider}`"
        )

        if provider == "ollama":
            st.markdown(
                "**Model:** "
                f"`{settings.ollama_model}`"
            )

            server_status = (
                check_ollama_server()
            )

            if server_status["running"]:
                st.success(
                    "Ollama server is running"
                )

                if server_status["version"]:
                    st.caption(
                        "Version: "
                        f"{server_status['version']}"
                    )

                model_status = (
                    check_configured_model()
                )

                if model_status["available"]:
                    st.success(
                        "Configured model is available"
                    )
                else:
                    st.error(
                        "Configured model is not installed"
                    )

                    if model_status[
                        "installed_models"
                    ]:
                        st.caption(
                            "Installed: "
                            + ", ".join(
                                model_status[
                                    "installed_models"
                                ]
                            )
                        )

            else:
                st.error(
                    "Ollama server is stopped"
                )

                if st.button(
                    "Start Ollama",
                    width="stretch",
                ):
                    startup = (
                        start_ollama_server()
                    )

                    if startup["error"]:
                        st.error(
                            startup["error"]
                        )
                    else:
                        with st.spinner(
                            "Starting Ollama..."
                        ):
                            for _ in range(15):
                                time.sleep(1)

                                if (
                                    check_ollama_server()[
                                        "running"
                                    ]
                                ):
                                    st.rerun()

                            st.error(
                                "Ollama did not become "
                                "available in time."
                            )

        st.divider()

        st.subheader("Dataset")

        st.markdown(
            "**Database:** Northwind SQLite"
        )

        st.markdown(
            "**Metrics:** net revenue, gross "
            "revenue, order count, quantity, AOV"
        )

        st.divider()

        if st.button(
            "Clear latest result",
            width="stretch",
        ):
            st.session_state[
                "workflow_result"
            ] = None

            st.session_state[
                "last_question"
            ] = ""

            st.rerun()

        history = st.session_state.get(
            "run_history",
            [],
        )

        if history:
            st.subheader("Recent questions")

            for item in reversed(
                history[-5:]
            ):
                st.caption(
                    item.get(
                        "question",
                        "",
                    )
                )


def render_header() -> None:
    st.title(
        "Multi-Agent Data Analytics System"
    )

    st.write(
        "Ask business questions about Northwind data. "
        "The system interprets the request, plans the "
        "analysis, generates validated SQL, evaluates "
        "the results, and creates an evidence-backed "
        "report."
    )


def render_question_form() -> None:
    with st.form(
        "analytics_question_form",
        clear_on_submit=False,
    ):
        question = st.text_area(
            "Business question",
            value=st.session_state.get(
                "last_question",
                "",
            ),
            placeholder=(
                "For example: Show the top five "
                "categories by revenue in Germany."
            ),
            height=100,
            key="question_input",
        )

        example_columns = st.columns(3)

        with example_columns[0]:
            st.caption("How many orders are there?")

        with example_columns[1]:
            st.caption(
                "Show the top five categories "
                "by revenue in Germany."
            )

        with example_columns[2]:
            st.caption(
                "Compare monthly sales for "
                "Beverages and Dairy Products."
            )

        submitted = st.form_submit_button(
            "Run analysis",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    cleaned_question = question.strip()

    if not cleaned_question:
        st.warning(
            "Enter a business question."
        )
        return

    if (
        settings.llm_provider.lower()
        == "ollama"
    ):
        server_status = check_ollama_server()

        if not server_status["running"]:
            st.error(
                "Ollama is not running. Start it from "
                "the sidebar before running analysis."
            )
            return

        model_status = (
            check_configured_model()
        )

        if not model_status["available"]:
            st.error(
                "The configured Ollama model is not "
                "installed: "
                f"{settings.ollama_model}"
            )
            return

    st.session_state[
        "workflow_running"
    ] = True

    st.session_state[
        "last_question"
    ] = cleaned_question

    with st.status(
        "Running the analytical workflow...",
        expanded=True,
    ) as status:
        try:
            st.write(
                "Understanding the business question"
            )

            result = run_workflow(
                cleaned_question
            )

            st.session_state[
                "workflow_result"
            ] = result

            st.session_state[
                "run_history"
            ].append(
                {
                    "question": cleaned_question,
                    "status": result.get(
                        "status",
                        "unknown",
                    ),
                    "request_id": result.get(
                        "request_id",
                    ),
                }
            )

            final_status = result.get(
                "status"
            )

            if final_status == "completed":
                status.update(
                    label=(
                        "Analysis completed"
                    ),
                    state="complete",
                    expanded=False,
                )

            elif final_status in {
    "needs_clarification",
    "unsupported",
    "unsupported_analysis",
    "unsupported_data",
    "needs_more_evidence",
    "no_data",
}:
                status.update(
                    label=(
                        "Workflow completed with "
                        f"status: {final_status}"
                    ),
                    state="complete",
                    expanded=False,
                )

            else:
                status.update(
                    label="Analysis failed",
                    state="error",
                    expanded=True,
                )

        except Exception as error:
            st.session_state[
                "workflow_result"
            ] = {
                "status": "failed",
                "errors": [
                    str(error)
                ],
                "warnings": [],
                "trace": [
                    (
                        "An unhandled application "
                        "error occurred."
                    )
                ],
            }

            status.update(
                label="Analysis failed",
                state="error",
                expanded=True,
            )

        finally:
            st.session_state[
                "workflow_running"
            ] = False


def render_latest_result() -> None:
    result = st.session_state.get(
        "workflow_result"
    )

    if not result:
        st.info(
            "Submit a business question to begin."
        )
        return

    st.divider()

    render_status(result)
    render_user_message(result)
    render_clarification(result)
    render_unsupported(result)
    render_clarification(result)
    render_unsupported(result)
    render_errors_and_warnings(result)

    final_report = result.get(
        "final_report"
    )

    if final_report:
        render_executive_report(
            final_report
        )

        render_visualizations(
            result
        )

    render_query_result(result)
    render_technical_details(result)


def main() -> None:
    initialize_session_state()
    render_sidebar()
    render_header()
    render_question_form()
    render_latest_result()


if __name__ == "__main__":
    main()