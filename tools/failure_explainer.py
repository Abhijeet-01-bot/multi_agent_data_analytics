from __future__ import annotations

from typing import Any


def explain_workflow_failure(
    state: dict[str, Any],
) -> str:
    errors = state.get(
        "errors",
        [],
    )

    latest_error = (
        errors[-1]
        if errors
        else "An unknown failure occurred."
    )

    lowered_error = latest_error.lower()

    if "sql parsing failed" in lowered_error:
        return (
            "I understood the question, but I could "
            "not create a valid SQLite query for this "
            "analytical shape. The generated query "
            "failed syntax validation, so it was not "
            "executed."
        )

    if "unknown table" in lowered_error:
        return (
            "I understood the question, but the local "
            "model referenced a table that does not "
            "exist in the Northwind schema. The query "
            "was blocked before execution."
        )

    if "no such column" in lowered_error:
        return (
            "I understood the question, but the generated "
            "query referenced a column that is not "
            "available in the selected Northwind table."
        )

    if (
        "missing_expected_column"
        in lowered_error
        or "expected column" in lowered_error
    ):
        return (
            "The database query ran, but it did not "
            "return the columns required to answer the "
            "question reliably."
        )

    if "empty_result" in lowered_error:
        return (
            "The question is valid, but no Northwind "
            "records matched the requested filters."
        )

    return (
        "I could not complete the analysis safely. "
        "The workflow stopped instead of presenting "
        "an unvalidated answer. Technical reason: "
        f"{latest_error}"
    )