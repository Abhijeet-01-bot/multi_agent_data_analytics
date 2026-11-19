from typing import Any

import pytest

from agents.analysis_agent import AnalysisAgent
from schemas.analysis_schemas import (
    AdditionalAnalysisTask,
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


class FakeStructuredAnalysisModel:
    def __init__(
        self,
        response: AnalysisResult | dict[str, Any],
    ) -> None:
        self.response = response
        self.received_input: object | None = None

    def invoke(
        self,
        input: object,
    ) -> AnalysisResult | dict[str, Any]:
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
                    "Retrieve and rank category "
                    "net revenue."
                ),
                task_type=TaskType.RANKING,
                metrics=["net_revenue"],
                dimensions=["category"],
                expected_columns=[
                    "CategoryName",
                    "NetRevenue",
                ],
            )
        ],
        confidence=1.0,
    )


def build_evidence_bundle() -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id="E-T1-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Category revenue ranking",
        description=(
            "Categories ranked by net revenue."
        ),
        calculation_name=(
            "Category revenue ranking"
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


def build_valid_analysis() -> AnalysisResult:
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
                    "Beverages had the highest "
                    "net revenue"
                ),
                description=(
                    "The validated ranking placed "
                    "Beverages first at 1000.0."
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


def test_analysis_agent_returns_findings() -> None:
    model = FakeStructuredAnalysisModel(
        build_valid_analysis()
    )

    agent = AnalysisAgent(
        structured_model=model
    )

    result = agent.analyze(
        intent=build_intent(),
        plan=build_plan(),
        evidence_bundle=(
            build_evidence_bundle()
        ),
    )

    assert result.evidence_sufficient is True
    assert len(result.findings) == 1
    assert result.findings[0].value == 1000.0
    assert model.received_input is not None


def test_dictionary_response_is_validated() -> None:
    response = (
        build_valid_analysis().model_dump(
            mode="json"
        )
    )

    agent = AnalysisAgent(
        structured_model=(
            FakeStructuredAnalysisModel(
                response
            )
        )
    )

    result = agent.analyze(
        intent=build_intent(),
        plan=build_plan(),
        evidence_bundle=(
            build_evidence_bundle()
        ),
    )

    assert isinstance(
        result,
        AnalysisResult,
    )


def test_unknown_evidence_id_is_rejected() -> None:
    response = build_valid_analysis()

    response.findings[0].evidence_ids = [
        "E-UNKNOWN-999"
    ]

    agent = AnalysisAgent(
        structured_model=(
            FakeStructuredAnalysisModel(
                response
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown evidence",
    ):
        agent.analyze(
            intent=build_intent(),
            plan=build_plan(),
            evidence_bundle=(
                build_evidence_bundle()
            ),
        )


def test_empty_evidence_is_rejected() -> None:
    empty_bundle = EvidenceBundle(
        request_id="REQ-EMPTY"
    )

    agent = AnalysisAgent(
        structured_model=(
            FakeStructuredAnalysisModel(
                build_valid_analysis()
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="at least one evidence",
    ):
        agent.analyze(
            intent=build_intent(),
            plan=build_plan(),
            evidence_bundle=empty_bundle,
        )


def test_insufficient_evidence_requests_task() -> None:
    response = AnalysisResult(
        analysis_summary=(
            "The current evidence shows a decline "
            "but not its main driver."
        ),
        findings=[
            AnalyticalFinding(
                finding_id="F1",
                finding_type=(
                    FindingType.OBSERVATION
                ),
                title="Revenue declined",
                description=(
                    "The validated evidence shows "
                    "a reduction."
                ),
                importance=(
                    FindingImportance.HIGH
                ),
                evidence_ids=[
                    "E-T1-RANKING-001"
                ],
                confidence=0.8,
            )
        ],
        evidence_sufficient=False,
        unanswered_questions=[
            (
                "Was the decline driven by price, "
                "quantity or discount?"
            )
        ],
        additional_tasks=[
            AdditionalAnalysisTask(
                description=(
                    "Compare price, quantity and "
                    "discount across periods."
                ),
                reason=(
                    "Current evidence does not identify "
                    "the decline driver."
                ),
                metrics=["net_revenue"],
                dimensions=["category"],
                expected_columns=[
                    "CategoryName",
                    "PreviousQuantity",
                    "CurrentQuantity",
                    "PreviousAveragePrice",
                    "CurrentAveragePrice",
                ],
            )
        ],
        confidence=0.75,
    )

    agent = AnalysisAgent(
        structured_model=(
            FakeStructuredAnalysisModel(
                response
            )
        )
    )

    result = agent.analyze(
        intent=build_intent(),
        plan=build_plan(),
        evidence_bundle=(
            build_evidence_bundle()
        ),
    )

    assert result.evidence_sufficient is False
    assert len(result.additional_tasks) == 1
    assert result.unanswered_questions
def test_generic_evidence_id_is_normalized() -> None:
    response = build_valid_analysis()

    response.findings[0].evidence_ids = [
        "data"
    ]

    agent = AnalysisAgent(
        structured_model=(
            FakeStructuredAnalysisModel(
                response
            )
        )
    )

    result = agent.analyze(
        intent=build_intent(),
        plan=build_plan(),
        evidence_bundle=(
            build_evidence_bundle()
        ),
    )

    assert (
        result.findings[0].evidence_ids
        == ["E-T1-RANKING-001"]
    )