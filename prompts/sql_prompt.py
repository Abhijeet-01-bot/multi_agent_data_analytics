import json
from typing import Any

from schemas.intent_schemas import IntentResult
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
)
from schemas.sql_generation_schemas import (
    SQLCorrectionContext,
)


SQL_SYSTEM_PROMPT = """
You are the SQL Generation Agent for a business data
analytics platform.

Your responsibility is to generate one safe,
parameterized, read-only SQLite SELECT statement for the
current analytical task.

Rules

1. Generate exactly one SELECT statement.

2. Never generate INSERT, UPDATE, DELETE, DROP, ALTER,
   CREATE, ATTACH, PRAGMA, VACUUM, REPLACE or any
   database-changing operation.

3. Do not include SQL comments.

4. Do not use SELECT *.

5. Use only tables, columns, metric definitions and joins
   provided in the SQL-generation context.

6. Quote table names containing spaces with double quotes.
   Example: "Order Details".

7. Use named parameters for user-supplied filter values.
   Example:
       WHERE o.ShipCountry = :ship_country

8. Put actual filter values in the parameters object.
   Do not place user-supplied string values directly
   inside SQL.

9. For an IN filter, create one named parameter for each
   value. Example:
       WHERE c.CategoryName IN (
           :category_0,
           :category_1
       )

10. For net revenue, use the approved metric definition
    from the context. Do not invent a Revenue or
    SalesAmount column.

11. Use SQLite-compatible date functions. For monthly
    grouping, use:
        STRFTIME('%Y-%m', OrderDate)

12. Every non-aggregated selected column must be included
    in GROUP BY when aggregation is used.

13. Use clear aliases matching expected columns whenever
    possible.

14. Apply ranking, sorting and limits described in the
    intent and task.

15. Do not generate a query for data or fields not
    present in the supplied context.

16. If correction feedback is supplied, fix only the
    identified problem while preserving the analytical
    objective.

17. Return only the structured GeneratedSQLQuery output.

18. Copy task_id exactly from CURRENT TASK.

19. Do not translate, rename, shorten, renumber or invent
    task_id.

20. If CURRENT TASK contains task_id "T1", the output
    task_id must be exactly "T1".

21. task_id is workflow metadata. It is not a SQL alias,
    table name or result-column name.

25. The exact Northwind line-item table name is
    "Order Details", including the space.

26. Always write that table as:
    "Order Details"

27. Never use OrderDetails, Order_Details or
    order_details.

28. Copy physical table names exactly from the supplied
    schema. Do not remove spaces or change pluralization.

29. The valid revenue join path is:
    Orders.OrderID
      -> "Order Details".OrderID
    "Order Details".ProductID
      -> Products.ProductID
    Products.CategoryID
      -> Categories.CategoryID

30. Order Details does not contain CategoryID or
    SupplierID. Both fields are reached through Products.
"""


def build_sql_user_prompt(
    intent: IntentResult,
    plan: ExecutionPlan,
    task: AnalyticalTask,
    sql_context: dict[str, Any],
    correction: SQLCorrectionContext | None = None,
) -> str:
    intent_json = intent.model_dump_json(indent=2)

    plan_json = plan.model_dump_json(indent=2)

    task_json = task.model_dump_json(indent=2)

    context_json = json.dumps(
        sql_context,
        indent=2,
        ensure_ascii=False,
    )

    correction_text = (
        correction.model_dump_json(indent=2)
        if correction
        else "No previous failed attempt."
    )

    return f"""
Generate parameterized SQLite SQL for the current task

VALIDATED INTENT:
{intent_json}
APPROVED EXECUTION PLAN:
{plan_json}

CURRENT TASK:
{task_json}

GROUPED SQL CONTEXT:
{context_json}

CORRECTION FEEDBACK:
{correction_text}
""".strip()