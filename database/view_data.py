import argparse

import pandas as pd
from sqlalchemy import inspect, text

from database.connection import get_engine


def list_tables() -> None:
    engine = get_engine()
    inspector = inspect(engine)

    print("\nAvailable tables:")

    for table_name in inspector.get_table_names():
        print(f"  - {table_name}")


def view_table(
    table_name: str,
    limit: int = 10,
) -> None:
    engine = get_engine()
    inspector = inspect(engine)

    available_tables = inspector.get_table_names()

    matching_table = next(
        (
            available_table
            for available_table in available_tables
            if available_table.lower() == table_name.lower()
        ),
        None,
    )

    if matching_table is None:
        raise ValueError(
            f"Table '{table_name}' was not found. "
            f"Available tables: {available_tables}"
        )

    safe_limit = max(1, min(limit, 100))

    escaped_table_name = matching_table.replace('"', '""')

    query = text(
        f'SELECT * FROM "{escaped_table_name}" '
        f"LIMIT {safe_limit}"
    )

    with engine.connect() as connection:
        dataframe = pd.read_sql_query(
            query,
            connection,
        )

    print(f"\nTable: {matching_table}")
    print(f"Showing first {len(dataframe)} rows:\n")

    print(dataframe.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="View tables from the Northwind database."
    )

    parser.add_argument(
        "--table",
        type=str,
        help='Table name, for example "Orders".',
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum rows to display. Default is 10.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available tables.",
    )

    arguments = parser.parse_args()

    if arguments.list:
        list_tables()
        return

    if arguments.table:
        view_table(
            table_name=arguments.table,
            limit=arguments.limit,
        )
        return

    list_tables()
    print(
        '\nUse --table "TableName" to display records.'
    )


if __name__ == "__main__":
    main()