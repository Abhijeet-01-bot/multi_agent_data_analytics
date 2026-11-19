from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from schemas.sql_schemas import SQLValidationResult
from tools.schema_loader import load_schema_catalog


BLOCKED_KEYWORDS = {
    "ALTER",
    "ATTACH",
    "CREATE",
    "DELETE",
    "DETACH",
    "DROP",
    "GRANT",
    "INSERT",
    "PRAGMA",
    "REINDEX",
    "REPLACE",
    "REVOKE",
    "TRUNCATE",
    "UPDATE",
    "VACUUM",
}

SQL_COMMENT_PATTERNS = (
    r"--",
    r"/\*",
    r"\*/",
)


def _normalize_identifier(identifier: str) -> str:
    """
    Normalize a database identifier for case-insensitive
    comparison.
    """

    return identifier.strip().lower()


def _load_allowed_tables() -> dict[str, str]:
    """
    Load valid table names from the schema catalog.

    Returns:
        A mapping such as:
        {
            "orders": "Orders",
            "order details": "Order Details"
        }
    """

    catalog = load_schema_catalog()
    tables = catalog.get("tables", {})

    return {
        _normalize_identifier(table_name): table_name
        for table_name in tables.keys()
    }


def _contains_blocked_keywords(
    sql: str,
) -> list[str]:
    """
    Return all blocked SQL keywords appearing in the query.
    """

    uppercase_sql = sql.upper()
    detected_keywords: list[str] = []

    for keyword in BLOCKED_KEYWORDS:
        pattern = rf"\b{re.escape(keyword)}\b"

        if re.search(pattern, uppercase_sql):
            detected_keywords.append(keyword)

    return sorted(detected_keywords)


def _contains_sql_comment(sql: str) -> bool:
    """
    Check whether generated SQL contains comments.
    """

    return any(
        re.search(pattern, sql)
        for pattern in SQL_COMMENT_PATTERNS
    )


def _extract_referenced_tables(
    expression: exp.Expression,
) -> list[str]:
    """
    Extract physical table names from the SQL syntax tree.

    CTE names are excluded because they are temporary query
    aliases rather than physical Northwind tables.
    """

    cte_names = {
        cte.alias_or_name
        for cte in expression.find_all(exp.CTE)
        if cte.alias_or_name
    }

    table_names: list[str] = []

    for table in expression.find_all(exp.Table):
        table_name = table.name

        if not table_name:
            continue

        if table_name in cte_names:
            continue

        table_names.append(table_name)

    return sorted(set(table_names))


def _find_unknown_tables(
    referenced_tables: list[str],
) -> list[str]:
    """
    Find tables that do not exist in the schema catalog.
    """

    allowed_tables = _load_allowed_tables()

    unknown_tables = [
        table_name
        for table_name in referenced_tables
        if _normalize_identifier(table_name)
        not in allowed_tables
    ]

    return sorted(set(unknown_tables))


def validate_sql(sql: str) -> SQLValidationResult:
    """
    Validate generated SQL before database execution.

    Rules:
    - Query cannot be empty.
    - SQL comments are rejected.
    - Dangerous keywords are rejected.
    - Only one SQL statement is allowed.
    - Only SELECT-style read operations are allowed.
    - Physical tables must exist in the schema catalog.
    """

    errors: list[str] = []
    warnings: list[str] = []

    cleaned_sql = sql.strip()

    if not cleaned_sql:
        return SQLValidationResult(
            is_valid=False,
            status="rejected",
            errors=["SQL query is empty."],
        )

    if _contains_sql_comment(cleaned_sql):
        errors.append(
            "SQL comments are not allowed in generated queries."
        )

    blocked_keywords = _contains_blocked_keywords(
        cleaned_sql
    )

    if blocked_keywords:
        errors.append(
            "Blocked SQL keyword detected: "
            + ", ".join(blocked_keywords)
        )

    try:
        statements = sqlglot.parse(
            cleaned_sql,
            read="sqlite",
        )

    except ParseError as error:
        errors.append(
            f"SQL parsing failed: {error}"
        )

        return SQLValidationResult(
            is_valid=False,
            status="rejected",
            errors=errors,
        )

    statements = [
        statement
        for statement in statements
        if statement is not None
    ]

    if len(statements) != 1:
        errors.append(
            "Exactly one SQL statement is allowed."
        )

        return SQLValidationResult(
            is_valid=False,
            status="rejected",
            errors=errors,
        )

    expression = statements[0]

    statement_type = (
        expression.key.upper()
        if expression.key
        else expression.__class__.__name__.upper()
    )

    # A top-level Select covers ordinary SELECT statements.
    # Queries beginning with WITH generally still parse as Select.
    if not isinstance(expression, exp.Select):
        errors.append(
            "Only read-only SELECT queries are allowed."
        )

    referenced_tables = _extract_referenced_tables(
        expression
    )

    unknown_tables = _find_unknown_tables(
        referenced_tables
    )

    if unknown_tables:
        errors.append(
            "Unknown table(s): "
            + ", ".join(unknown_tables)
        )

    if not referenced_tables:
        warnings.append(
            "The query does not reference a physical database table."
        )

    normalized_sql = expression.sql(
        dialect="sqlite",
        pretty=True,
    )

    if errors:
        return SQLValidationResult(
            is_valid=False,
            status="rejected",
            normalized_sql=normalized_sql,
            statement_type=statement_type,
            referenced_tables=referenced_tables,
            errors=errors,
            warnings=warnings,
        )

    return SQLValidationResult(
        is_valid=True,
        status="approved",
        normalized_sql=normalized_sql,
        statement_type=statement_type,
        referenced_tables=referenced_tables,
        errors=[],
        warnings=warnings,
    )