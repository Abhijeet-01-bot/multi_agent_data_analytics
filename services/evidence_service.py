from __future__ import annotations

from uuid import uuid4

from schemas.analytics_schemas import (
    AnalyticsResult,
)
from schemas.evidence_schemas import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceType,
)
from schemas.result_validation_schemas import (
    ResultValidationResult,
)
from schemas.sql_generation_schemas import (
    SQLTaskResult,
)


def _new_evidence_id(
    prefix: str,
) -> str:
    short_id = uuid4().hex[:8].upper()

    return f"{prefix}-{short_id}"


def create_query_evidence(
    sql_task_result: SQLTaskResult,
    validation_result: ResultValidationResult,
) -> EvidenceRecord:
    if not sql_task_result.success:
        raise ValueError(
            "Query evidence cannot be created from "
            "an unsuccessful SQL task."
        )

    if sql_task_result.query is None:
        raise ValueError(
            "The SQL task does not contain a query."
        )

    if sql_task_result.execution is None:
        raise ValueError(
            "The SQL task does not contain an "
            "execution result."
        )

    evidence_warnings = [
        issue.message
        for issue in validation_result.issues
        if issue.severity.value == "warning"
    ]

    validated_rows = (
        validation_result.validated_rows
    )

    if len(validated_rows) > 100:
        evidence_warnings.append(
            "Only the first 100 validated rows were "
            "included in the LLM evidence context."
        )

    return EvidenceRecord(
        evidence_id=_new_evidence_id(
            f"E-{sql_task_result.task_id}-QUERY"
        ),
        task_id=sql_task_result.task_id,
        evidence_type=(
            EvidenceType.QUERY_RESULT
        ),
        title=(
            f"Validated query result for "
            f"{sql_task_result.task_id}"
        ),
        description=(
            f"The query returned "
            f"{validation_result.row_count} validated "
            "row or rows."
        ),
        source_sql=(
            sql_task_result.query.sql
        ),
        source_parameters=(
            sql_task_result.query.parameters
        ),
        source_columns=(
            validation_result.actual_columns
        ),
        source_rows=validated_rows[:100],
        validated=(
            validation_result.is_valid
        ),
        warnings=evidence_warnings,
    )


def create_calculation_evidence(
    task_id: str,
    calculation_name: str,
    description: str,
    inputs: dict,
    analytics_result: AnalyticsResult,
) -> EvidenceRecord:
    """
    Convert a deterministic analytics result into an
    evidence record.
    """

    return EvidenceRecord(
        evidence_id=_new_evidence_id(
            f"E-{task_id}-CALC"
        ),
        task_id=task_id,
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title=calculation_name,
        description=description,
        calculation_name=calculation_name,
        calculation_inputs=inputs,
        calculation_output=(
            analytics_result.model_dump(
                mode="json"
            )
        ),
        validated=analytics_result.success,
        warnings=analytics_result.warnings,
    )


def build_evidence_bundle(
    request_id: str,
    records: list[EvidenceRecord],
) -> EvidenceBundle:
    """
    Build a request-level evidence collection.
    """

    validated_count = sum(
        1
        for record in records
        if record.validated
    )

    warnings: list[str] = []

    for record in records:
        warnings.extend(record.warnings)

    return EvidenceBundle(
        request_id=request_id,
        records=records,
        record_count=len(records),
        validated_record_count=(
            validated_count
        ),
        warnings=warnings,
    )