from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from database.connection import get_engine
from schemas.sql_schemas import QueryExecutionResult
from tools.sql_validator import validate_sql


ABSOLUTE_MAX_ROWS = 50_000


def _serialize_value(value: Any) -> Any:
    """
    Convert database values into JSON-compatible values.
    """

    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


def _serialize_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert all values in a result row into serializable
    Python values.
    """

    return {
        key: _serialize_value(value)
        for key, value in row.items()
    }


def execute_read_only_query(
    sql: str,
    parameters: dict[str, Any] | None = None,
    max_rows: int | None = None,
) -> QueryExecutionResult:
    """
    Validate and execute a read-only SQL query.

    The query is never executed if validation fails.
    """

    validation = validate_sql(sql)

    if not validation.is_valid:
        return QueryExecutionResult(
            success=False,
            status="validation_failed",
            sql=sql,
            validation=validation,
            errors=validation.errors,
            warnings=validation.warnings,
        )

    effective_max_rows = (
        max_rows
        if max_rows is not None
        else settings.max_query_rows
    )

    effective_max_rows = max(
        1,
        min(
            effective_max_rows,
            ABSOLUTE_MAX_ROWS,
        ),
    )

    engine = get_engine()
    query_parameters = parameters or {}

    start_time = time.perf_counter()

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(sql),
                query_parameters,
            )

            columns = list(result.keys())

            fetched_rows = (
                result.mappings().fetchmany(
                    effective_max_rows + 1
                )
            )

        execution_time_ms = round(
            (
                time.perf_counter()
                - start_time
            )
            * 1000,
            2,
        )

        truncated = (
            len(fetched_rows)
            > effective_max_rows
        )

        returned_rows = fetched_rows[
            :effective_max_rows
        ]

        serialized_rows = [
            _serialize_row(dict(row))
            for row in returned_rows
        ]

        warnings = list(validation.warnings)

        if truncated:
            warnings.append(
                "The query result was truncated to "
                f"{effective_max_rows} rows."
            )

        return QueryExecutionResult(
            success=True,
            status="completed",
            columns=columns,
            rows=serialized_rows,
            returned_row_count=len(serialized_rows),
            truncated=truncated,
            execution_time_ms=execution_time_ms,
            sql=validation.normalized_sql or sql,
            validation=validation,
            errors=[],
            warnings=warnings,
        )

    except SQLAlchemyError as error:
        execution_time_ms = round(
            (
                time.perf_counter()
                - start_time
            )
            * 1000,
            2,
        )

        return QueryExecutionResult(
            success=False,
            status="execution_failed",
            execution_time_ms=execution_time_ms,
            sql=sql,
            validation=validation,
            errors=[
                f"Database execution failed: {error}"
            ],
            warnings=validation.warnings,
        )