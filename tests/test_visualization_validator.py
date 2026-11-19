from schemas.evidence_schemas import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceType,
)
from schemas.visualization_schemas import (
    VisualizationSpec,
    VisualizationType,
)
from tools.visualization_validator import (
    extract_visualization_rows,
    validate_visualization_spec,
)


def build_bundle() -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id="E-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Ranking",
        description="Category ranking.",
        calculation_output={
            "records": [
                {
                    "label": "Beverages",
                    "value": 1000.0,
                },
                {
                    "label": "Confections",
                    "value": 800.0,
                },
            ]
        },
        validated=True,
    )

    return EvidenceBundle(
        request_id="REQ-001",
        records=[record],
        record_count=1,
        validated_record_count=1,
    )


def build_spec() -> VisualizationSpec:
    return VisualizationSpec(
        visualization_id="V1",
        chart_type=(
            VisualizationType.HORIZONTAL_BAR
        ),
        title="Revenue by Category",
        description="Category ranking.",
        evidence_id="E-RANKING-001",
        x_field="value",
        y_field="label",
    )


def test_valid_visualization_spec() -> None:
    result = validate_visualization_spec(
        spec=build_spec(),
        evidence_bundle=build_bundle(),
    )

    assert result.is_valid is True
    assert result.missing_fields == []


def test_missing_evidence_is_invalid() -> None:
    spec = build_spec()
    spec.evidence_id = "E-MISSING"

    result = validate_visualization_spec(
        spec=spec,
        evidence_bundle=build_bundle(),
    )

    assert result.is_valid is False
    assert result.errors


def test_missing_field_is_invalid() -> None:
    spec = build_spec()
    spec.x_field = "MissingValue"

    result = validate_visualization_spec(
        spec=spec,
        evidence_bundle=build_bundle(),
    )

    assert result.is_valid is False

    assert "MissingValue" in (
        result.missing_fields
    )


def test_extract_visualization_rows() -> None:
    rows = extract_visualization_rows(
        spec=build_spec(),
        evidence_bundle=build_bundle(),
    )

    assert len(rows) == 2
    assert rows[0]["label"] == "Beverages"


def test_large_top_n_creates_warning() -> None:
    spec = build_spec()
    spec.top_n = 10

    result = validate_visualization_spec(
        spec=spec,
        evidence_bundle=build_bundle(),
    )

    assert result.is_valid is True
    assert result.warnings