from pathlib import Path

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
from tools.visualization_tool import (
    create_plotly_figure,
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
                    "Rank category revenue."
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

    evidence_record = EvidenceRecord(
        evidence_id="E-T1-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Category revenue ranking",
        description=(
            "Validated category revenue ranking."
        ),
        calculation_output={
            "records": [
                {
                    "rank": 1,
                    "label": "Beverages",
                    "value": 120000.0,
                },
                {
                    "rank": 2,
                    "label": "Confections",
                    "value": 100000.0,
                },
                {
                    "rank": 3,
                    "label": "Seafood",
                    "value": 80000.0,
                },
            ]
        },
        validated=True,
    )

    evidence_bundle = EvidenceBundle(
        request_id="REQ-REPORT-DEMO",
        records=[evidence_record],
        record_count=1,
        validated_record_count=1,
    )

    analysis = AnalysisResult(
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
                    "validated category revenue."
                ),
                importance=(
                    FindingImportance.HIGH
                ),
                evidence_ids=[
                    "E-T1-RANKING-001"
                ],
                metric="net_revenue",
                dimension="category",
                value=120000.0,
                confidence=1.0,
            )
        ],
        evidence_sufficient=True,
        confidence=0.98,
    )

    reporting_agent = ReportingAgent()

    report = reporting_agent.create_report(
        intent=intent,
        plan=plan,
        analysis=analysis,
        evidence_bundle=evidence_bundle,
    )

    print("\nEXECUTIVE REPORT")
    print("=" * 80)

    print(
        report.model_dump_json(
            indent=2
        )
    )

    output_directory = Path(
        "outputs/charts"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for visualization in report.visualizations:
        figure = create_plotly_figure(
            spec=visualization,
            evidence_bundle=(
                evidence_bundle
            ),
        )

        output_path = (
            output_directory
            / (
                f"{visualization.visualization_id}"
                ".html"
            )
        )

        figure.write_html(
            str(output_path)
        )

        print(
            "\nCreated chart: "
            f"{output_path}"
        )


if __name__ == "__main__":
    main()