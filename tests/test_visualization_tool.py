import plotly.graph_objects as go

from schemas.evidence_schemas import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceType,
)
from schemas.visualization_schemas import (
    SortOrder,
    VisualizationSpec,
    VisualizationType,
)
from tools.visualization_tool import (
    create_plotly_figure,
)


def build_bundle() -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id="E-RANKING-001",
        task_id="T1",
        evidence_type=(
            EvidenceType.CALCULATION
        ),
        title="Category ranking",
        description="Validated category ranking.",
        calculation_output={
            "records": [
                {
                    "label": "Seafood",
                    "value": 200.0,
                },
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


def test_create_horizontal_bar() -> None:
    spec = VisualizationSpec(
        visualization_id="V1",
        chart_type=(
            VisualizationType.HORIZONTAL_BAR
        ),
        title="Category Revenue",
        description="Revenue ranking.",
        evidence_id="E-RANKING-001",
        x_field="value",
        y_field="label",
        sort_order=SortOrder.DESCENDING,
        top_n=2,
        show_values=True,
    )

    figure = create_plotly_figure(
        spec=spec,
        evidence_bundle=build_bundle(),
    )

    assert isinstance(
        figure,
        go.Figure,
    )

    assert len(figure.data) == 1

    assert list(
        figure.data[0].x
    ) == [
        1000.0,
        800.0,
    ]


def test_create_table() -> None:
    spec = VisualizationSpec(
        visualization_id="V2",
        chart_type=(
            VisualizationType.TABLE
        ),
        title="Category Data",
        description="Exact category values.",
        evidence_id="E-RANKING-001",
    )

    figure = create_plotly_figure(
        spec=spec,
        evidence_bundle=build_bundle(),
    )

    assert isinstance(
        figure,
        go.Figure,
    )

    assert len(figure.data) == 1


def test_create_kpi() -> None:
    kpi_record = EvidenceRecord(
        evidence_id="E-KPI-001",
        task_id="T2",
        evidence_type=(
            EvidenceType.QUERY_RESULT
        ),
        title="Order count",
        description="Validated order count.",
        source_rows=[
            {
                "OrderCount": 830
            }
        ],
        validated=True,
    )

    bundle = EvidenceBundle(
        request_id="REQ-KPI",
        records=[kpi_record],
        record_count=1,
        validated_record_count=1,
    )

    spec = VisualizationSpec(
        visualization_id="V3",
        chart_type=(
            VisualizationType.KPI
        ),
        title="Total Orders",
        description="Total order count.",
        evidence_id="E-KPI-001",
        value_field="OrderCount",
    )

    figure = create_plotly_figure(
        spec=spec,
        evidence_bundle=bundle,
    )

    assert isinstance(
        figure,
        go.Figure,
    )

    assert figure.data[0].value == 830