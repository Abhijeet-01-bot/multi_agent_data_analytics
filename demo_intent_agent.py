from agents.intent_agent import (
    IntentUnderstandingAgent,
)
import traceback


DEMO_QUESTIONS = [
    (
        "Show the top five categories by "
        "revenue in Germany."
    ), ("Show top five categories by net revenue."),
    (
        "Compare monthly sales for Beverages "
        "and Dairy Products."
    ),
    (
        "Show net revenue for orders shipped "
        "to country XYZ_NONEXISTENT."
    ),
]


def main() -> None:
    agent = IntentUnderstandingAgent()

    for question in DEMO_QUESTIONS:
        print("\n" + "=" * 80)
        print(f"QUESTION: {question}")
        print("-" * 80)

        try:
            result = agent.analyze(question)

            print(
                result.model_dump_json(
                    indent=2
                )
            )

        except Exception as error:
            print(
        f"Intent analysis failed: {error}"
    )

            traceback.print_exc()


if __name__ == "__main__":
    main()