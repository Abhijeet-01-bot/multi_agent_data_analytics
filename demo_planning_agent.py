from agents.intent_agent import (
    IntentUnderstandingAgent,
)
from agents.planning_agent import PlanningAgent


DEMO_QUESTIONS = [
    (
        "Show the top five categories by "
        "revenue in Germany."
    ),
    (
        "Compare monthly sales for Beverages "
        "and Dairy Products."
    ),
    "How many orders are there?",
    "Why did performance fall?",
    "Predict the stock market tomorrow.",
]


def main() -> None:
    intent_agent = IntentUnderstandingAgent()
    planning_agent = PlanningAgent()

    for question in DEMO_QUESTIONS:
        print("\n" + "=" * 80)
        print(f"QUESTION: {question}")
        print("=" * 80)

        try:
            intent = intent_agent.analyze(
                question
            )

            print("\nINTENT")
            print("-" * 80)

            print(
                intent.model_dump_json(
                    indent=2
                )
            )

            if intent.clarification_required:
                print("\nPLANNING STOPPED")
                print("-" * 80)
                print(
                    "Clarification required: "
                    f"{intent.clarification_question}"
                )
                continue

            if intent.unsupported_request:
                print("\nPLANNING STOPPED")
                print("-" * 80)
                print(
                    "Unsupported request: "
                    f"{intent.unsupported_reason}"
                )
                continue

            plan = planning_agent.create_plan(
                intent
            )

            print("\nEXECUTION PLAN")
            print("-" * 80)

            print(
                plan.model_dump_json(
                    indent=2
                )
            )

        except Exception as error:
            print("\nWORKFLOW ERROR")
            print("-" * 80)
            print(str(error))


if __name__ == "__main__":
    main()