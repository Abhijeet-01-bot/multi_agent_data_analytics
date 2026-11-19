from __future__ import annotations

from uuid import uuid4

from agents.analysis_agent import (
    AnalysisAgent,
)
from agents.intent_agent import (
    IntentUnderstandingAgent,
)
from agents.planning_agent import (
    PlanningAgent,
)
from agents.reporting_agent import (
    ReportingAgent,
)
from agents.sql_agent import (
    SQLGenerationAgent,
)
from graph.state import (
    AnalyticsWorkflowState,
)
from schemas.analysis_schemas import (
    AnalysisResult,
)
from schemas.analytics_schemas import (
    AnalyticsResult,
)
from schemas.evidence_schemas import (
    EvidenceBundle,
)
from schemas.intent_schemas import (
    AnalysisType,
    IntentResult,
)
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
    TaskType,
)
from schemas.result_validation_schemas import (
    ResultValidationResult,
)
from schemas.sql_generation_schemas import (
    SQLTaskResult,
)
from services.evidence_service import (
    build_evidence_bundle,
    create_calculation_evidence,
    create_query_evidence,
)
from tools.analytics_tools import (
    analyze_ranking,
)
from tools.result_validator import (
    validate_query_result,
)
from schemas.capability_schemas import (
    SupportStatus,
)
from tools.capability_registry import (
    assess_capability,
)
from tools.failure_explainer import (
    explain_workflow_failure,
)

DATABASE_TASK_TYPES = {
    TaskType.DATA_RETRIEVAL,
    TaskType.AGGREGATION,
    TaskType.FILTERING,
    TaskType.RANKING,
    TaskType.COMPARISON,
    TaskType.TREND_ANALYSIS,
    TaskType.CONTRIBUTION_ANALYSIS,
    TaskType.ANOMALY_DETECTION,
}


def initialize_request_node(
    state: AnalyticsWorkflowState,
) -> dict:
    request_id = state.get(
        "request_id"
    )

    if not request_id:
        request_id = (
            f"REQ-{uuid4().hex[:10].upper()}"
        )

    return {
        "request_id": request_id,
        "status": "running",
        "current_node": "initialize_request",
        "clarification_required": False,
        "clarification_question": None,
        "unsupported_request": False,
        "unsupported_reason": None,
        "evidence_sufficient": False,
        "replan_count": state.get(
            "replan_count",
            0,
        ),
        "max_replans": state.get(
            "max_replans",
            1,
        ),
        "trace": [
            "Workflow initialized."
        ],
    }


def intent_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        agent = IntentUnderstandingAgent()

        intent = agent.analyze(
            state["user_question"]
        )

        return {
            "status": "running",
            "current_node": "intent",
            "intent": intent.model_dump(
                mode="json"
            ),
            "clarification_required": (
                intent.clarification_required
            ),
            "clarification_question": (
                intent.clarification_question
            ),
            "unsupported_request": (
                intent.unsupported_request
            ),
            "unsupported_reason": (
                intent.unsupported_reason
            ),
            "trace": [
                "Intent Agent completed."
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "intent",
            "errors": [
                f"Intent Agent failed: {error}"
            ],
            "trace": [
                "Intent Agent failed."
            ],
        }


def clarification_node(
    state: AnalyticsWorkflowState,
) -> dict:
    return {
        "status": "needs_clarification",
        "current_node": "clarification",
        "trace": [
            (
                "Workflow stopped because user "
                "clarification is required."
            )
        ],
    }
def no_data_node(
    state: AnalyticsWorkflowState,
) -> dict:
    return {
        "status": "no_data",
        "current_node": "no_data",
        "user_message": (
            state.get("user_message")
            or (
                "The request is valid, but no "
                "matching Northwind records were "
                "found."
            )
        ),
        "trace": [
            (
                "Workflow completed without matching "
                "data."
            )
        ],
    }

def unsupported_node(
    state: AnalyticsWorkflowState,
) -> dict:
    return {
        "status": "unsupported",
        "current_node": "unsupported",
        "trace": [
            (
                "Workflow stopped because the "
                "request is unsupported."
            )
        ],
    }


def planning_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        agent = PlanningAgent()

        plan = agent.create_plan(
            intent
        )

        return {
            "status": "running",
            "current_node": "planning",
            "plan": plan.model_dump(
                mode="json"
            ),
            "trace": [
                "Planning Agent completed."
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "planning",
            "errors": [
                f"Planning Agent failed: {error}"
            ],
            "trace": [
                "Planning Agent failed."
            ],
        }


def select_task_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        plan = ExecutionPlan.model_validate(
            state["plan"]
        )

        executable_tasks = [
            task
            for task in plan.tasks
            if (
                task.required_tables
                or task.task_type
                in DATABASE_TASK_TYPES
            )
        ]

        if not executable_tasks:
            raise ValueError(
                "The plan does not contain an "
                "executable database task."
            )

        selected_task = executable_tasks[0]

        return {
            "status": "running",
            "current_node": "select_task",
            "selected_task": (
                selected_task.model_dump(
                    mode="json"
                )
            ),
            "trace": [
                (
                    f"Selected task "
                    f"{selected_task.task_id}."
                )
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "select_task",
            "errors": [
                f"Task selection failed: {error}"
            ],
            "trace": [
                "Task selection failed."
            ],
        }


def sql_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        plan = ExecutionPlan.model_validate(
            state["plan"]
        )

        task = AnalyticalTask.model_validate(
            state["selected_task"]
        )

        agent = SQLGenerationAgent()

        result = agent.run_task(
            intent=intent,
            plan=plan,
            task=task,
        )

        update = {
            "current_node": "sql",
            "sql_task_result": (
                result.model_dump(
                    mode="json"
                )
            ),
            "trace": [
                (
                    "SQL Agent completed after "
                    f"{result.attempts} attempt(s)."
                )
            ],
        }

        if result.success:
            update["status"] = "running"
        else:
            update["status"] = "failed"
            update["errors"] = result.errors

        return update

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "sql",
            "errors": [
                f"SQL Agent failed: {error}"
            ],
            "trace": [
                "SQL Agent failed."
            ],
        }


def validate_result_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        task = AnalyticalTask.model_validate(
            state["selected_task"]
        )

        sql_result = (
            SQLTaskResult.model_validate(
                state["sql_task_result"]
            )
        )

        # Use the executed SQL query's output contract.
        if (
            sql_result.query is not None
            and sql_result.query.expected_columns
        ):
            task.expected_columns = list(
                sql_result.query.expected_columns
            )

        if sql_result.execution is None:
            raise ValueError(
                "The SQL task does not contain an "
                "execution result."
            )

        validation = validate_query_result(
            task=task,
            execution=sql_result.execution,
        )

        validation_data = (
            validation.model_dump(
                mode="json"
            )
        )

        # An empty result is different from a technical
        # failure. The SQL was valid and executed, but no
        # rows matched the requested filters.
        issue_codes = {
            issue.code
            for issue in validation.issues
        }

        if (
            validation.empty_result
            or "EMPTY_RESULT" in issue_codes
        ):
            return {
                "status": "no_data",
                "current_node": (
                    "validate_result"
                ),
                "result_validation": (
                    validation_data
                ),
                "user_message": (
                    "The request is valid, but no "
                    "matching Northwind records were "
                    "found for the requested filters."
                ),
                "trace": [
                    (
                        "The query completed "
                        "successfully but returned "
                        "no rows."
                    )
                ],
            }

        validation_errors = [
            issue.message
            for issue in validation.issues
            if issue.severity.value == "error"
        ]

        validation_warnings = [
            issue.message
            for issue in validation.issues
            if issue.severity.value == "warning"
        ]

        update = {
            "current_node": (
                "validate_result"
            ),
            "result_validation": (
                validation_data
            ),
            "warnings": (
                validation_warnings
            ),
            "trace": [
                (
                    "Result validation completed. "
                    f"Valid: {validation.is_valid}."
                )
            ],
        }

        if validation.is_valid:
            update["status"] = "running"

        else:
            update["status"] = "failed"
            update["errors"] = (
                validation_errors
            )

        return update

    except Exception as error:
        return {
            "status": "failed",
            "current_node": (
                "validate_result"
            ),
            "errors": [
                (
                    "Result validation failed: "
                    f"{error}"
                )
            ],
            "trace": [
                "Result validation failed."
            ],
        }

def analytics_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        task = AnalyticalTask.model_validate(
            state["selected_task"]
        )

        validation = (
            ResultValidationResult.model_validate(
                state["result_validation"]
            )
        )

        sql_result = (
            SQLTaskResult.model_validate(
                state["sql_task_result"]
            )
        )

        analysis_type_values = {
            analysis_type.value
            for analysis_type
            in intent.analysis_types
        }

        expected_columns = list(
            validation.actual_columns
        )

        if (
            sql_result.query is not None
            and sql_result.query.expected_columns
        ):
            expected_columns = list(
                sql_result.query.expected_columns
            )

        analytics_result = None

        if (
            AnalysisType.RANKING.value
            in analysis_type_values
            and len(expected_columns) >= 2
        ):
            label_column = expected_columns[0]
            value_column = expected_columns[1]

            analytics_result = analyze_ranking(
                rows=validation.validated_rows,
                label_column=label_column,
                value_column=value_column,
                descending=(
                    intent.sort_direction is None
                    or intent.sort_direction.value
                    == "descending"
                ),
                limit=intent.limit,
            )

        if analytics_result is None:
            return {
                "status": "running",
                "current_node": "analytics",
                "analytics_result": None,
                "trace": [
                    (
                        "No additional deterministic "
                        "analytics were required."
                    )
                ],
            }

        update = {
            "current_node": "analytics",
            "analytics_result": (
                analytics_result.model_dump(
                    mode="json"
                )
            ),
            "warnings": (
                analytics_result.warnings
            ),
            "trace": [
                (
                    "Deterministic analytics "
                    "completed."
                )
            ],
        }

        if analytics_result.success:
            update["status"] = "running"
        else:
            update["status"] = "failed"
            update["errors"] = (
                analytics_result.errors
            )

        return update

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "analytics",
            "errors": [
                (
                    "Deterministic analytics failed: "
                    f"{error}"
                )
            ],
            "trace": [
                (
                    "Deterministic analytics failed."
                )
            ],
        }

def evidence_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        sql_result = (
            SQLTaskResult.model_validate(
                state["sql_task_result"]
            )
        )

        validation = (
            ResultValidationResult.model_validate(
                state["result_validation"]
            )
        )

        records = [
            create_query_evidence(
                sql_task_result=sql_result,
                validation_result=validation,
            )
        ]

        analytics_data = state.get(
            "analytics_result"
        )

        if analytics_data:
            analytics_result = (
                AnalyticsResult.model_validate(
                    analytics_data
                )
            )

            task = (
                AnalyticalTask.model_validate(
                    state["selected_task"]
                )
            )

            records.append(
                create_calculation_evidence(
                    task_id=task.task_id,
                    calculation_name=(
                        "Deterministic task analysis"
                    ),
                    description=(
                        "Deterministic analysis of the "
                        "validated query result."
                    ),
                    inputs={
                        "expected_columns": (
                            task.expected_columns
                        )
                    },
                    analytics_result=(
                        analytics_result
                    ),
                )
            )

        bundle = build_evidence_bundle(
            request_id=state["request_id"],
            records=records,
        )

        return {
            "status": "running",
            "current_node": "evidence",
            "evidence_bundle": (
                bundle.model_dump(
                    mode="json"
                )
            ),
            "warnings": bundle.warnings,
            "trace": [
                (
                    f"Created {bundle.record_count} "
                    "evidence record(s)."
                )
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "evidence",
            "errors": [
                (
                    "Evidence creation failed: "
                    f"{error}"
                )
            ],
            "trace": [
                "Evidence creation failed."
            ],
        }


def analysis_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        plan = ExecutionPlan.model_validate(
            state["plan"]
        )

        evidence_bundle = (
            EvidenceBundle.model_validate(
                state["evidence_bundle"]
            )
        )

        deterministic_analysis = (
            _build_ranking_analysis(
                state
            )
        )

        if deterministic_analysis is not None:
            analysis = deterministic_analysis
        else:
            agent = AnalysisAgent()

            analysis = agent.analyze(
                intent=intent,
                plan=plan,
                evidence_bundle=(
                    evidence_bundle
                ),
            )

        return {
            "status": "running",
            "current_node": "analysis",
            "analysis_result": (
                analysis.model_dump(
                    mode="json"
                )
            ),
            "evidence_sufficient": (
                analysis.evidence_sufficient
            ),
            "warnings": analysis.warnings,
            "trace": [
                "Analysis Agent completed."
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "analysis",
            "errors": [
                (
                    "Analysis Agent failed: "
                    f"{error}"
                )
            ],
            "trace": [
                "Analysis Agent failed."
            ],
        }


def needs_more_evidence_node(
    state: AnalyticsWorkflowState,
) -> dict:
    analysis = state.get(
        "analysis_result"
    ) or {}

    additional_tasks = analysis.get(
        "additional_tasks",
        [],
    )

    return {
        "status": "needs_more_evidence",
        "current_node": "needs_more_evidence",
        "replan_count": (
            state.get(
                "replan_count",
                0,
            )
            + 1
        ),
        "warnings": [
            (
                "Additional analytical evidence is "
                "required before final reporting."
            )
        ],
        "trace": [
            (
                "Analysis requested "
                f"{len(additional_tasks)} additional "
                "task(s)."
            )
        ],
    }


def reporting_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        plan = ExecutionPlan.model_validate(
            state["plan"]
        )

        analysis = AnalysisResult.model_validate(
            state["analysis_result"]
        )

        evidence_bundle = (
            EvidenceBundle.model_validate(
                state["evidence_bundle"]
            )
        )

        agent = ReportingAgent()

        report = agent.create_report(
            intent=intent,
            plan=plan,
            analysis=analysis,
            evidence_bundle=evidence_bundle,
        )

        return {
            "status": "completed",
            "current_node": "reporting",
            "final_report": report.model_dump(
                mode="json"
            ),
            "trace": [
                "Reporting Agent completed."
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "reporting",
            "errors": [
                (
                    "Reporting Agent failed: "
                    f"{error}"
                )
            ],
            "trace": [
                "Reporting Agent failed."
            ],
        }


def failure_node(
    state: AnalyticsWorkflowState,
) -> dict:
    existing_errors = state.get(
        "errors"
    ) or []

    latest_error = (
        existing_errors[-1]
        if existing_errors
        else "Unknown workflow failure."
    )

    return {
        "status": "failed",
        "current_node": "failure",
        "trace": [
            (
                "Workflow stopped due to failure: "
                f"{latest_error}"
            )
        ],
    }

def _build_ranking_analysis(
    state: AnalyticsWorkflowState,
) -> AnalysisResult | None:
    analytics_data = state.get(
        "analytics_result"
    )

    evidence_data = state.get(
        "evidence_bundle"
    )

    intent_data = state.get(
        "intent"
    )

    if (
        not analytics_data
        or not evidence_data
        or not intent_data
    ):
        return None

    analytics_result = (
        AnalyticsResult.model_validate(
            analytics_data
        )
    )

    intent = IntentResult.model_validate(
        intent_data
    )

    if (
        analytics_result.operation.value
        != "ranking"
        or not analytics_result.records
    ):
        return None

    bundle = EvidenceBundle.model_validate(
        evidence_data
    )

    calculation_records = [
        record
        for record in bundle.records
        if (
            record.validated
            and record.evidence_type.value
            == "calculation"
        )
    ]

    if not calculation_records:
        return None

    top_record = (
        analytics_result.records[0]
    )

    label = str(
        top_record.get(
            "label",
            "Top result",
        )
    )

    value = float(
        top_record.get(
            "value",
            0.0,
        )
    )

    from schemas.analysis_schemas import (
        AnalyticalFinding,
        FindingImportance,
        FindingType,
    )

    return AnalysisResult(
        analysis_summary=(
            f"{label} ranked first among the "
            "validated results."
        ),
        findings=[
            AnalyticalFinding(
                finding_id="F1",
                finding_type=(
                    FindingType.OBSERVATION
                ),
                title=(
                    f"{label} ranked first"
                ),
                description=(
                    f"{label} had the highest "
                    f"validated value at {value:.2f}."
                ),
                importance=(
                    FindingImportance.HIGH
                ),
                evidence_ids=[
                    calculation_records[
                        0
                    ].evidence_id
                ],
                metric=(
                    intent.metrics[0]
                    if intent.metrics
                    else None
                ),
                dimension=(
                    intent.dimensions[0]
                    if intent.dimensions
                    else None
                ),
                value=value,
                confidence=1.0,
            )
        ],
        evidence_sufficient=True,
        unanswered_questions=[],
        additional_tasks=[],
        limitations=[
            (
                "The ranking is descriptive and does "
                "not establish causation or predict "
                "future performance."
            )
        ],
        warnings=[],
        confidence=1.0,
    )

def capability_node(
    state: AnalyticsWorkflowState,
) -> dict:
    try:
        intent = IntentResult.model_validate(
            state["intent"]
        )

        assessment = assess_capability(
            intent
        )

        return {
            "status": "running",
            "current_node": "capability",
            "capability_assessment": (
                assessment.model_dump(
                    mode="json"
                )
            ),
            "support_status": (
                assessment
                .support_status
                .value
            ),
            "user_message": (
                assessment.reason
            ),
            "suggested_questions": (
                assessment
                .suggested_questions
            ),
            "trace": [
                (
                    "Capability assessment "
                    f"completed: "
                    f"{assessment.support_status.value}."
                )
            ],
        }

    except Exception as error:
        return {
            "status": "failed",
            "current_node": "capability",
            "errors": [
                (
                    "Capability assessment failed: "
                    f"{error}"
                )
            ],
            "trace": [
                (
                    "Capability assessment failed."
                )
            ],
        }


def unsupported_analysis_node(
    state: AnalyticsWorkflowState,
) -> dict:
    assessment = (
        state.get(
            "capability_assessment"
        )
        or {}
    )

    return {
        "status": "unsupported_analysis",
        "current_node": (
            "unsupported_analysis"
        ),
        "user_message": assessment.get(
            "reason"
        ),
        "suggested_questions": (
            assessment.get(
                "suggested_questions",
                [],
            )
        ),
        "trace": [
            (
                "Workflow stopped because the "
                "requested analytical method is not "
                "implemented safely."
            )
        ],
    }


def unsupported_data_node(
    state: AnalyticsWorkflowState,
) -> dict:
    assessment = (
        state.get(
            "capability_assessment"
        )
        or {}
    )

    return {
        "status": "unsupported_data",
        "current_node": "unsupported_data",
        "user_message": assessment.get(
            "reason"
        ),
        "suggested_questions": (
            assessment.get(
                "suggested_questions",
                [],
            )
        ),
        "trace": [
            (
                "Workflow stopped because the "
                "required data is unavailable."
            )
        ],
    }

def failure_node(
    state: AnalyticsWorkflowState,
) -> dict:
    return {
        "status": "failed",
        "current_node": "failure",
        "user_message": (
            explain_workflow_failure(
                dict(state)
            )
        ),
        "trace": [
            (
                "Workflow stopped after a "
                "controlled validation failure."
            )
        ],
    }