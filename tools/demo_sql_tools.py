from pprint import pprint

from tools.query_executor import (
    execute_read_only_query,
)
from tools.sql_validator import validate_sql


def demonstrate_validation() -> None:
    queries = {
        "Safe query": """
            SELECT
                CategoryID,
                CategoryName
            FROM Categories
            ORDER BY CategoryName
        """,
        "Unknown table": """
            SELECT *
            FROM Sales
        """,
        "Unsafe delete": """
            DELETE FROM Orders
        """,
    }

    print("\nSQL VALIDATION DEMONSTRATION")
    print("=" * 60)

    for query_name, sql in queries.items():
        print(f"\n{query_name}")
        print("-" * 60)

        result = validate_sql(sql)

        pprint(
            result.model_dump(),
            sort_dicts=False,
        )


def demonstrate_execution() -> None:
    sql = """
        SELECT
            c.CategoryName,
            ROUND(
                SUM(
                    od.UnitPrice
                    * od.Quantity
                    * (1 - od.Discount)
                ),
                2
            ) AS NetRevenue
        FROM "Order Details" AS od
        JOIN Products AS p
            ON od.ProductID = p.ProductID
        JOIN Categories AS c
            ON p.CategoryID = c.CategoryID
        GROUP BY
            c.CategoryID,
            c.CategoryName
        ORDER BY
            NetRevenue DESC
    """

    print("\nQUERY EXECUTION DEMONSTRATION")
    print("=" * 60)

    result = execute_read_only_query(sql)

    print(f"Success: {result.success}")
    print(f"Status: {result.status}")
    print(
        "Execution time: "
        f"{result.execution_time_ms} ms"
    )
    print(
        "Returned rows: "
        f"{result.returned_row_count}"
    )
    print(f"Truncated: {result.truncated}")

    print("\nRevenue by category:")

    for row in result.rows:
        print(
            f"  {row['CategoryName']:<25} "
            f"{row['NetRevenue']:>12}"
        )

    if result.errors:
        print("\nErrors:")

        for error in result.errors:
            print(f"  - {error}")

    if result.warnings:
        print("\nWarnings:")

        for warning in result.warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    demonstrate_validation()
    demonstrate_execution()