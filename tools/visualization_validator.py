from __future__ import annotations

from typing import Any

from schemas.evidence_schemas import (
    EvidenceBundle,
    EvidenceRecord,
)
from schemas.visualization_schemas import (
    VisualizationSpec,
    VisualizationValidationResult,
)


def _extract_evidence_rows(
    evidence: EvidenceRecord,
) -> list[dict[str, Any]]:
    """
    Extract tabular records from either query evidence or
    deterministic calculation evidence.
    """

    if evidence.source_rows:
        return evidence.source_rows

    calculation_output = (
        evidence.calculation_output
    )

    records = calculation_output.get(
        "records",
        [],
    )

    if isinstance(records, list):
        return [
            record
            for record in records
            if isinstance(record, dict)
        ]

    return []


def _required_fields(
    spec: VisualizationSpec,
) -> list[str]:
    fields = [
        spec.x_field,
        spec.y_field,
        spec.category_field,
        spec.series_field,
        spec.value_field,
        spec.label_field,
    ]

    return sorted(
        {
            field
            for field in fields
            if field
        }
    )


def validate_visualization_spec(
    spec: VisualizationSpec,
    evidence_bundle: EvidenceBundle,
) -> VisualizationValidationResult:
    evidence = next(
        (
            record
            for record
            in evidence_bundle.records
            if (
                record.evidence_id
                == spec.evidence_id
            )
        ),
        None,
    )

    if evidence is None:
        return VisualizationValidationResult(
            is_valid=False,
            visualization_id=(
                spec.visualization_id
            ),
            errors=[
                (
                    "Referenced evidence record "
                    f"{spec.evidence_id} does not exist."
                )
            ],
        )

    if not evidence.validated:
        return VisualizationValidationResult(
            is_valid=False,
            visualization_id=(
                spec.visualization_id
            ),
            errors=[
                "The referenced evidence is not validated."
            ],
        )

    rows = _extract_evidence_rows(
        evidence
    )

    if not rows:
        return VisualizationValidationResult(
            is_valid=False,
            visualization_id=(
                spec.visualization_id
            ),
            errors=[
                "The referenced evidence does not "
                "contain tabular records."
            ],
        )

    available_fields = sorted(
        {
            field
            for row in rows
            for field in row.keys()
        }
    )

    required_fields = _required_fields(
        spec
    )

    missing_fields = sorted(
        set(required_fields)
        - set(available_fields)
    )

    errors: list[str] = []
    warnings: list[str] = []

    if missing_fields:
        errors.append(
            "The visualization references missing "
            "field or fields: "
            + ", ".join(missing_fields)
        )

    if (
        spec.top_n is not None
        and spec.top_n > len(rows)
    ):
        warnings.append(
            "The requested top_n is greater than "
            "the number of available records."
        )

    return VisualizationValidationResult(
        is_valid=not errors,
        visualization_id=(
            spec.visualization_id
        ),
        available_fields=available_fields,
        missing_fields=missing_fields,
        errors=errors,
        warnings=warnings,
    )


def extract_visualization_rows(
    spec: VisualizationSpec,
    evidence_bundle: EvidenceBundle,
) -> list[dict[str, Any]]:
    validation = validate_visualization_spec(
        spec=spec,
        evidence_bundle=evidence_bundle,
    )

    if not validation.is_valid:
        raise ValueError(
            "; ".join(validation.errors)
        )

    evidence = next(
        record
        for record in evidence_bundle.records
        if (
            record.evidence_id
            == spec.evidence_id
        )
    )

    return _extract_evidence_rows(
        evidence
    )