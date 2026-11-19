from agents.intent_agent import (
    IntentUnderstandingAgent,
)
from agents.planning_agent import PlanningAgent
from agents.sql_agent import SQLGenerationAgent
from schemas.planning_schemas import TaskType


DEMO_QUESTIONS = [
    (
        "Show the top five categories by "
        "revenue in Germany."
    ),
    "How many orders are there?",
]


DATABASE_TASK_TYPES = {
    TaskType.DATA_RETRIEVAL,
    TaskType.AGGREGATION,
    TaskType.FILTERING,
    TaskType.COMPARISON,
    TaskType.TREND_ANALYSIS,
    TaskType.CONTRIBUTION_ANALYSIS,
    TaskType.ANOMALY_DETECTION,
}


def main() -> None:
    intent_agent = IntentUnderstandingAgent()
    planning_agent = PlanningAgent()
    sql_agent = SQLGenerationAgent()

    for question in DEMO_QUESTIONS:
        print("\n" + "=" * 80)
        print(f"QUESTION: {question}")
        print("=" * 80)

        try:
            intent = intent_agent.analyze(
                question
            )

            print("\nINTENT")
            print(intent.model_dump_json(indent=2))

            if intent.clarification_required:
                print(
                    "\nSTOPPED: "
                    f"{intent.clarification_question}"
                )
                continue

            if intent.unsupported_request:
                print(
                    "\nSTOPPED: "
                    f"{intent.unsupported_reason}"
                )
                continue

            plan = planning_agent.create_plan(
                intent
            )

            print("\nPLAN")
            print(plan.model_dump_json(indent=2))

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
                print(
                    "\nNo database task was produced."
                )
                continue

            task = executable_tasks[0]

            result = sql_agent.run_task(
                intent=intent,
                plan=plan,
                task=task,
            )

            print("\nSQL TASK RESULT")
            print(
                result.model_dump_json(
                    indent=2
                )
            )

            if (
                result.success
                and result.execution
            ):
                print("\nRETURNED DATA")

                for row in (
                    result.execution.rows
                ):
                    print(row)

        except Exception as error:
            print("\nWORKFLOW ERROR")
            print(str(error))


if __name__ == "__main__":
    main()