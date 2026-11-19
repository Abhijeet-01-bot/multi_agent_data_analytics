from typing import Any

import pytest

from agents.reporting_agent import (
    ReportingAgent,
)
from schemas.analysis_schemas import (
    AnalyticalFinding,
    AnalysisResult,
    FindingImportance,
    FindingType,
)
from schemas.evidence_schemas import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceType,
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
from schemas.report_schemas import (
    BusinessRecommendation,
    ExecutiveReport,
    RecommendationPriority,
    ReportFinding,
)
from schemas.visualization_schemas import (
    SortOrder,
    VisualizationSpec,
    VisualizationType,
)


class FakeStructuredReportingModel:
    def __init__(
        self,
        response: ExecutiveReport | dict[str, Any],
    ) -> None:
        self.response = response
        self.received_input: object | None = None

    def invoke(
        self,
        input: object,
    ) -> ExecutiveReport | dict[str, Any]:
        self.received_input = input
        return self.response


def build_intent() -> IntentResult:
    return IntentResult(
        business_objective=(
            "Rank categories by net revenue."
        ),
        metrics=["net_revenue"],
        dimensions=["category"],
        analysis_types=[
            AnalysisType.RANKING
        ],
        confidence=1.0,
    )


def build_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_summary=(
            "Rank categories by net revenue."
        ),
        tasks=[
            AnalyticalTask(
                task_id="T1",
                description=(
                    "Rank category net revenue."
                ),
                task_type=TaskType.RANKING,
                metrics=["net_revenue"],
                dimensions=["category"],
                expected_columns=[
                    "label",
                    "value",
                ],
            )
        ],
        confidence=1.0,
    )


def build_analysis() -> AnalysisResult:
    return AnalysisResult(
        analysis_summary=(
            "Beverages ranked first by net revenue."
        ),
        findings=[
            AnalyticalFinding(
                finding_id="F1",
                finding_type=(
                    FindingType.OBSERVATION
                ),
                title=(
                    "Beverages ranked first"
                ),
                description=(
                    "Beverages had the highest "
                    "validated net revenue."
                ),
                importance=(
                    FindingImportance.HIGH
                ),
                evidence_ids=[
                    "E-T1-RANKING-001"
                ],
                metric="net_revenue",
                dimension="category",
                value=1000.0,
                confidence=1.0,
            )
        ],
        evidence_sufficient=True,
        confidence=0.98,
    )


def build_evidence() -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id="E-T1-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Category revenue ranking",
        description=(
            "Validated revenue ranking."
        ),
        calculation_output={
            "success": True,
            "records": [
                {
                    "rank": 1,
                    "label": "Beverages",
                    "value": 1000.0,
                },
                {
                    "rank": 2,
                    "label": "Confections",
                    "value": 800.0,
                },
            ],
        },
        validated=True,
    )

    return EvidenceBundle(
        request_id="REQ-001",
        records=[record],
        record_count=1,
        validated_record_count=1,
    )


def build_report() -> ExecutiveReport:
    return ExecutiveReport(
        report_title=(
            "Category Net Revenue Analysis"
        ),
        executive_summary=(
            "Beverages ranked first by net revenue "
            "in the validated category result."
        ),
        findings=[
            ReportFinding(
                finding_id="F1",
                title="Beverages ranked first",
                explanation=(
                    "Beverages had the largest "
                    "validated net revenue value."
                ),
                importance="high",
                evidence_ids=[
                    "E-T1-RANKING-001"
                ],
            )
        ],
        recommendations=[
            BusinessRecommendation(
                recommendation_id="R1",
                action=(
                    "Review the product mix within "
                    "the leading category."
                ),
                rationale=(
                    "The category ranks first in "
                    "validated net revenue."
                ),
                priority=(
                    RecommendationPriority.MEDIUM
                ),
                related_finding_ids=["F1"],
                evidence_ids=[
                    "E-T1-RANKING-001"
                ],
                limitation=(
                    "The evidence does not establish "
                    "future demand."
                ),
            )
        ],
        visualizations=[
            VisualizationSpec(
                visualization_id="V1",
                chart_type=(
                    VisualizationType.HORIZONTAL_BAR
                ),
                title=(
                    "Categories by Net Revenue"
                ),
                description=(
                    "Ranks category revenue values."
                ),
                evidence_id=(
                    "E-T1-RANKING-001"
                ),
                x_field="value",
                y_field="label",
                sort_order=(
                    SortOrder.DESCENDING
                ),
                show_values=True,
            )
        ],
        limitations=[
            (
                "The results describe historical "
                "Northwind transactions."
            )
        ],
        methodology_summary=(
            "The report uses validated query results "
            "and deterministic ranking calculations."
        ),
        evidence_ids_used=[
            "E-T1-RANKING-001"
        ],
        confidence=0.98,
    )


def test_reporting_agent_returns_report() -> None:
    model = FakeStructuredReportingModel(
        build_report()
    )

    agent = ReportingAgent(
        structured_model=model
    )

    result = agent.create_report(
        intent=build_intent(),
        plan=build_plan(),
        analysis=build_analysis(),
        evidence_bundle=build_evidence(),
    )

    assert isinstance(
        result,
        ExecutiveReport,
    )

    assert len(result.findings) == 1
    assert len(result.visualizations) == 1
    assert model.received_input is not None


def test_dictionary_report_is_validated() -> None:
    model = FakeStructuredReportingModel(
        build_report().model_dump(
            mode="json"
        )
    )

    agent = ReportingAgent(
        structured_model=model
    )

    result = agent.create_report(
        intent=build_intent(),
        plan=build_plan(),
        analysis=build_analysis(),
        evidence_bundle=build_evidence(),
    )

    assert isinstance(
        result,
        ExecutiveReport,
    )


def test_insufficient_analysis_is_rejected() -> None:
    analysis = build_analysis()
    analysis.evidence_sufficient = False
    analysis.unanswered_questions = [
        "Additional evidence is required."
    ]

    agent = ReportingAgent(
        structured_model=(
            FakeStructuredReportingModel(
                build_report()
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="insufficient",
    ):
        agent.create_report(
            intent=build_intent(),
            plan=build_plan(),
            analysis=analysis,
            evidence_bundle=build_evidence(),
        )


def test_unknown_evidence_is_rejected() -> None:
    report = build_report()

    report.visualizations[
        0
    ].evidence_id = "E-UNKNOWN"

    agent = ReportingAgent(
        structured_model=(
            FakeStructuredReportingModel(
                report
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown or unvalidated evidence",
    ):
        agent.create_report(
            intent=build_intent(),
            plan=build_plan(),
            analysis=build_analysis(),
            evidence_bundle=build_evidence(),
        )


def test_unknown_finding_is_rejected() -> None:
    report = build_report()

    report.recommendations[
        0
    ].related_finding_ids = [
        "F-UNKNOWN"
    ]

    agent = ReportingAgent(
        structured_model=(
            FakeStructuredReportingModel(
                report
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown finding",
    ):
        agent.create_report(
            intent=build_intent(),
            plan=build_plan(),
            analysis=build_analysis(),
            evidence_bundle=build_evidence(),
        )

def test_local_report_visualization_is_normalized() -> None:
    incomplete_local_report = {
        "report_title": (
            "Category Revenue Ranking"
        ),
        "executive_summary": (
            "Beverages ranked first."
        ),
        "findings": [
            {
                "finding_id": "F1",
                "title": (
                    "Beverages ranked first"
                ),
                "explanation": (
                    "Beverages had the highest "
                    "validated revenue."
                ),
                "importance": "high",
                "evidence_ids": [
                    "E-T1-RANKING-001"
                ],
            }
        ],
        "recommendations": [],
        "visualizations": [
            {
                "visualization_id": "V1",
                "chart_type": (
                    "horizontal_bar"
                ),
                "title": (
                    "Category Revenue Ranking"
                ),
                "description": (
                    "Ranks categories by revenue."
                ),
                "evidence_id": (
                    "E-T1-RANKING-001"
                ),
                "x_axis_title": (
                    "Net Revenue"
                ),
                "y_axis_title": "Category",
                "show_values": True,
            }
        ],
        "limitations": [],
        "methodology_summary": (
            "Uses validated evidence."
        ),
        "evidence_ids_used": [
            "E-T1-RANKING-001"
        ],
        "warnings": [],
        "confidence": 0.95,
    }

    model = FakeStructuredReportingModel(
        incomplete_local_report
    )

    agent = ReportingAgent(
        structured_model=model
    )

    result = agent.create_report(
        intent=build_intent(),
        plan=build_plan(),
        analysis=build_analysis(),
        evidence_bundle=build_evidence(),
    )

    visualization = result.visualizations[0]

    assert visualization.x_field == "value"
    assert visualization.y_field == "label"

def test_missing_visualization_gets_fallback() -> None:
    local_report = {
        "report_title": (
            "Category Revenue Ranking"
        ),
        "executive_summary": (
            "Beverages ranked first."
        ),
        "findings": [
            {
                "finding_id": "F1",
                "title": (
                    "Beverages ranked first"
                ),
                "explanation": (
                    "Beverages had the highest "
                    "validated category revenue."
                ),
                "importance": "high",
                "evidence_ids": [
                    "E-T1-RANKING-001"
                ],
            }
        ],
        "recommendations": [],
        "visualizations": [],
        "limitations": [],
        "methodology_summary": (
            "Uses validated evidence."
        ),
        "evidence_ids_used": [],
        "warnings": [],
        "confidence": 0.98,
    }

    agent = ReportingAgent(
        structured_model=(
            FakeStructuredReportingModel(
                local_report
            )
        )
    )

    result = agent.create_report(
        intent=build_intent(),
        plan=build_plan(),
        analysis=build_analysis(),
        evidence_bundle=build_evidence(),
    )

    assert len(result.visualizations) == 1

    visualization = result.visualizations[0]

    assert (
        visualization.chart_type.value
        == "horizontal_bar"
    )

    assert visualization.x_field == "value"
    assert visualization.y_field == "label"

    assert (
        visualization.evidence_id
        == "E-T1-RANKING-001"
    )

def test_evidence_ids_used_are_derived() -> None:
    local_report = {
        "report_title": (
            "Category Revenue Ranking"
        ),
        "executive_summary": (
            "Beverages ranked first."
        ),
        "findings": [
            {
                "finding_id": "F1",
                "title": (
                    "Beverages ranked first"
                ),
                "explanation": (
                    "Beverages had the highest "
                    "validated category revenue."
                ),
                "importance": "high",
                "evidence_ids": [
                    "E-T1-RANKING-001"
                ],
            }
        ],
        "recommendations": [],
        "visualizations": [],
        "limitations": [],
        "methodology_summary": (
            "Uses validated evidence."
        ),
        "evidence_ids_used": [],
        "warnings": [],
        "confidence": 0.98,
    }

    agent = ReportingAgent(
        structured_model=(
            FakeStructuredReportingModel(
                local_report
            )
        )
    )

    result = agent.create_report(
        intent=build_intent(),
        plan=build_plan(),
        analysis=build_analysis(),
        evidence_bundle=build_evidence(),
    )

    assert result.evidence_ids_used == [
        "E-T1-RANKING-001"
    ]