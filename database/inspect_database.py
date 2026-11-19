from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from database.connection import get_engine


def inspect_database() -> None:
    engine = get_engine()
    inspector = inspect(engine)

    table_names = inspector.get_table_names()

    print(f"Database contains {len(table_names)} tables.")

    for table_name in table_names:
        print(f"\nTable: {table_name}")

        columns = inspector.get_columns(table_name)

        for column in columns:
            nullable = column.get("nullable", True)

            print(
                f"  {column['name']:<25} "
                f"{str(column['type']):<15} "
                f"nullable={nullable}"
            )

        primary_key = inspector.get_pk_constraint(table_name)
        primary_columns = primary_key.get(
            "constrained_columns",
            [],
        )

        if primary_columns:
            print(f"  Primary key: {primary_columns}")

        foreign_keys = inspector.get_foreign_keys(table_name)

        for foreign_key in foreign_keys:
            print(
                "  Foreign key: "
                f"{foreign_key.get('constrained_columns')} "
                f"-> {foreign_key.get('referred_table')}."
                f"{foreign_key.get('referred_columns')}"
            )


def run_database_checks() -> None:
    engine = get_engine()

    checks = {
        "Total orders": """
            SELECT COUNT(*) AS value
            FROM Orders
        """,
        "Total customers": """
            SELECT COUNT(*) AS value
            FROM Customers
        """,
        "Total products": """
            SELECT COUNT(*) AS value
            FROM Products
        """,
        "Total order lines": """
            SELECT COUNT(*) AS value
            FROM "Order Details"
        """,
        "Net revenue": """
            SELECT ROUND(
                SUM(
                    UnitPrice
                    * Quantity
                    * (1 - Discount)
                ),
                2
            ) AS value
            FROM "Order Details"
        """,
        "Earliest order date": """
            SELECT MIN(OrderDate) AS value
            FROM Orders
        """,
        "Latest order date": """
            SELECT MAX(OrderDate) AS value
            FROM Orders
        """,
    }

    print("\nDatabase validation checks:")

    try:
        with engine.connect() as connection:
            for check_name, sql in checks.items():
                result = connection.execute(text(sql))
                row = result.mappings().first()
                value = row["value"] if row else None

                print(f"  {check_name:<25}: {value}")

    except SQLAlchemyError as error:
        print("\nDatabase check failed.")
        print(f"Reason: {error}")
        raise


def test_relationships() -> None:
    engine = get_engine()

    query = text("""
        SELECT
            o.OrderID,
            o.OrderDate,
            c.CompanyName AS CustomerName,
            p.ProductName,
            cat.CategoryName,
            od.Quantity,
            od.UnitPrice,
            od.Discount,
            ROUND(
                od.UnitPrice
                * od.Quantity
                * (1 - od.Discount),
                2
            ) AS NetRevenue
        FROM Orders AS o
        JOIN Customers AS c
            ON o.CustomerID = c.CustomerID
        JOIN "Order Details" AS od
            ON o.OrderID = od.OrderID
        JOIN Products AS p
            ON od.ProductID = p.ProductID
        JOIN Categories AS cat
            ON p.CategoryID = cat.CategoryID
        ORDER BY o.OrderDate
        LIMIT 5
    """)

    print("\nRelationship test:")

    with engine.connect() as connection:
        rows = connection.execute(query).mappings().all()

    for row in rows:
        print(
            f"  Order={row['OrderID']} | "
            f"Customer={row['CustomerName']} | "
            f"Product={row['ProductName']} | "
            f"Category={row['CategoryName']} | "
            f"Revenue={row['NetRevenue']}"
        )


if __name__ == "__main__":
    inspect_database()
    run_database_checks()
    test_relationships()