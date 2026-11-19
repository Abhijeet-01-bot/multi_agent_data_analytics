from agents.analysis_agent import (
    AnalysisAgent,
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


def main() -> None:
    intent = IntentResult(
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

    plan = ExecutionPlan(
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

    ranking_evidence = EvidenceRecord(
        evidence_id="E-T1-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Category revenue ranking",
        description=(
            "Validated categories ranked by net revenue."
        ),
        calculation_name=(
            "Category revenue ranking"
        ),
        calculation_output={
            "success": True,
            "operation": "ranking",
            "records": [
                {
                    "rank": 1,
                    "label": "Beverages",
                    "value": 120000.0,
                    "percentage_of_total": 40.0,
                },
                {
                    "rank": 2,
                    "label": "Confections",
                    "value": 100000.0,
                    "percentage_of_total": 33.3333,
                },
                {
                    "rank": 3,
                    "label": "Seafood",
                    "value": 80000.0,
                    "percentage_of_total": 26.6667,
                },
            ],
        },
        validated=True,
    )

    evidence_bundle = EvidenceBundle(
        request_id="REQ-DEMO-001",
        records=[ranking_evidence],
        record_count=1,
        validated_record_count=1,
    )

    agent = AnalysisAgent()

    result = agent.analyze(
        intent=intent,
        plan=plan,
        evidence_bundle=evidence_bundle,
    )

    print("\nANALYSIS RESULT")
    print("=" * 80)

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()