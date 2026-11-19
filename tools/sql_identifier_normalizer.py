from __future__ import annotations

import re


TABLE_NAME_ALIASES = {
    "OrderDetails": "Order Details",
    "Order_Details": "Order Details",
    "orderdetails": "Order Details",
    "order_details": "Order Details",
}


def normalize_sql_identifiers(
    sql: str,
) -> tuple[str, list[str]]:
    """
    Normalize only explicitly approved table-name aliases.

    This does not allow unknown tables. It converts common
    local-model variants to the exact physical Northwind
    table name before SQL validation.
    """

    normalized_sql = sql
    corrections: list[str] = []

    for alias, physical_name in (
        TABLE_NAME_ALIASES.items()
    ):
        # Match an identifier as a complete token,
        # optionally surrounded by SQL identifier quotes.
        pattern = re.compile(
            rf'(?<![A-Za-z0-9_])'
            rf'(?:"{re.escape(alias)}"|'
            rf'`{re.escape(alias)}`|'
            rf'\[{re.escape(alias)}\]|'
            rf'{re.escape(alias)})'
            rf'(?![A-Za-z0-9_])',
            flags=re.IGNORECASE,
        )

        replacement = f'"{physical_name}"'

        updated_sql, replacement_count = (
            pattern.subn(
                replacement,
                normalized_sql,
            )
        )

        if replacement_count > 0:
            corrections.append(
                f"Normalized table identifier "
                f"{alias} to "
                f'"{physical_name}".'
            )

            normalized_sql = updated_sql

    return normalized_sql, corrections

def normalize_table_names(
    table_names: list[str],
) -> list[str]:
    """
    Normalize table metadata using the same approved
    alias map.
    """

    normalized_names: list[str] = []

    aliases_by_lowercase = {
        alias.lower(): physical_name
        for alias, physical_name
        in TABLE_NAME_ALIASES.items()
    }

    for table_name in table_names:
        cleaned_name = (
            str(table_name)
            .strip()
            .strip('"')
            .strip("`")
            .strip("[")
            .strip("]")
        )

        normalized_name = (
            aliases_by_lowercase.get(
                cleaned_name.lower(),
                cleaned_name,
            )
        )

        if (
            normalized_name
            not in normalized_names
        ):
            normalized_names.append(
                normalized_name
            )

    return normalized_names