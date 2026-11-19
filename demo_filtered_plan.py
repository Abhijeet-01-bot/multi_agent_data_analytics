from agents.planning_agent import (
    PlanningAgent,
)
from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
)


def main() -> None:
    intent = IntentResult(
        business_objective=(
            "Calculate net revenue for orders "
            "shipped to XYZ_NONEXISTENT."
        ),
        metrics=[
            "net_revenue"
        ],
        dimensions=[],
        filters=[
            IntentFilter(
                field="ship_country",
                operator="equals",
                value=(
                    "XYZ_NONEXISTENT"
                ),
            )
        ],
        analysis_types=[
            AnalysisType.AGGREGATION
        ],
        confidence=1.0,
    )

    plan = (
        PlanningAgent
        ._build_deterministic_plan(
            intent
        )
    )

    if plan is None:
        print(
            "No deterministic plan matched."
        )

        return

    print(
        plan.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()