import json

from graph.workflow import (
    analytics_workflow,
)


DEMO_QUESTIONS = [
    (
        "Show the top five categories by "
        "revenue in Germany."
    ),("Show top five categories by net revenue"),
    (
        "Show net revenue for orders shipped "
        "to country XYZ_NONEXISTENT."
    ),
]


def print_final_result(
    result: dict,
) -> None:
    print("\nFINAL STATUS")
    print("-" * 80)
    print(
        result.get(
            "status",
            "unknown",
        )
    )

    print("\nWORKFLOW TRACE")
    print("-" * 80)

    for step in result.get(
        "trace",
        [],
    ):
        print(f"- {step}")

    if result.get(
        "clarification_required"
    ):
        print("\nCLARIFICATION REQUIRED")
        print("-" * 80)

        print(
            result.get(
                "clarification_question"
            )
        )

    if result.get(
        "unsupported_request"
    ):
        print("\nUNSUPPORTED REQUEST")
        print("-" * 80)

        print(
            result.get(
                "unsupported_reason"
            )
        )

    errors = result.get(
        "errors",
        [],
    )

    if errors:
        print("\nERRORS")
        print("-" * 80)

        for error in errors:
            print(f"- {error}")

    warnings = result.get(
        "warnings",
        [],
    )

    if warnings:
        print("\nWARNINGS")
        print("-" * 80)

        for warning in warnings:
            print(f"- {warning}")

    final_report = result.get(
        "final_report"
    )

    if final_report:
        print("\nFINAL REPORT")
        print("-" * 80)

        print(
            json.dumps(
                final_report,
                indent=2,
                ensure_ascii=False,
            )
        )

    if (
        result.get("status")
        == "needs_more_evidence"
    ):
        print("\nADDITIONAL ANALYSIS REQUIRED")
        print("-" * 80)

        analysis = result.get(
            "analysis_result"
        ) or {}

        for task in analysis.get(
            "additional_tasks",
            [],
        ):
            print(
                "- "
                + task.get(
                    "description",
                    "Additional task",
                )
            )


def main() -> None:
    for question in DEMO_QUESTIONS:
        print("\n" + "=" * 80)
        print(f"QUESTION: {question}")
        print("=" * 80)

        initial_state = {
            "user_question": question,
            "errors": [],
            "warnings": [],
            "trace": [],
            "replan_count": 0,
            "max_replans": 1,
        }

        result = analytics_workflow.invoke(
            initial_state,
            config={
                "recursion_limit": 30
            },
        )

        print_final_result(
            result
        )


if __name__ == "__main__":
    main()