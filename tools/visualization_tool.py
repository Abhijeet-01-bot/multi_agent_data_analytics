from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from schemas.evidence_schemas import (
    EvidenceBundle,
)
from schemas.visualization_schemas import (
    SortOrder,
    VisualizationSpec,
    VisualizationType,
)
from tools.visualization_validator import (
    extract_visualization_rows,
)


def _prepare_dataframe(
    spec: VisualizationSpec,
    evidence_bundle: EvidenceBundle,
) -> pd.DataFrame:
    rows = extract_visualization_rows(
        spec=spec,
        evidence_bundle=evidence_bundle,
    )

    dataframe = pd.DataFrame(rows)

    sort_field = (
        spec.y_field
        if spec.chart_type
        == VisualizationType.BAR
        else spec.x_field
    )

    if (
        spec.chart_type
        == VisualizationType.HORIZONTAL_BAR
    ):
        sort_field = spec.x_field

    if (
        spec.sort_order
        and sort_field
        and sort_field in dataframe.columns
    ):
        dataframe = dataframe.sort_values(
            by=sort_field,
            ascending=(
                spec.sort_order
                == SortOrder.ASCENDING
            ),
            kind="stable",
        )

    if spec.top_n is not None:
        dataframe = dataframe.head(
            spec.top_n
        )

    return dataframe


def create_plotly_figure(
    spec: VisualizationSpec,
    evidence_bundle: EvidenceBundle,
) -> go.Figure:
    """
    Create a Plotly figure from a validated visualization
    specification and evidence record.
    """

    dataframe = _prepare_dataframe(
        spec=spec,
        evidence_bundle=evidence_bundle,
    )

    if spec.chart_type == VisualizationType.BAR:
        figure = px.bar(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            title=spec.title,
            text=(
                spec.y_field
                if spec.show_values
                else None
            ),
        )

    elif (
        spec.chart_type
        == VisualizationType.HORIZONTAL_BAR
    ):
        figure = px.bar(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            orientation="h",
            title=spec.title,
            text=(
                spec.x_field
                if spec.show_values
                else None
            ),
        )

    elif spec.chart_type == VisualizationType.LINE:
        figure = px.line(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            title=spec.title,
            markers=True,
        )

    elif (
        spec.chart_type
        == VisualizationType.STACKED_BAR
    ):
        figure = px.bar(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            title=spec.title,
            barmode="stack",
        )

    elif (
        spec.chart_type
        == VisualizationType.SCATTER
    ):
        figure = px.scatter(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            title=spec.title,
        )

    elif (
        spec.chart_type
        == VisualizationType.HISTOGRAM
    ):
        figure = px.histogram(
            dataframe,
            x=spec.x_field,
            color=spec.series_field,
            title=spec.title,
        )

    elif spec.chart_type == VisualizationType.BOX:
        figure = px.box(
            dataframe,
            x=spec.x_field,
            y=spec.y_field,
            color=spec.series_field,
            title=spec.title,
        )

    elif (
        spec.chart_type
        == VisualizationType.WATERFALL
    ):
        figure = go.Figure(
            go.Waterfall(
                x=dataframe[
                    spec.x_field
                ].tolist(),
                y=dataframe[
                    spec.y_field
                ].tolist(),
            )
        )

        figure.update_layout(
            title=spec.title
        )

    elif spec.chart_type == VisualizationType.KPI:
        value = dataframe[
            spec.value_field
        ].iloc[0]

        figure = go.Figure(
            go.Indicator(
                mode="number",
                value=float(value),
                title={
                    "text": spec.title
                },
            )
        )

    elif spec.chart_type == VisualizationType.TABLE:
        figure = go.Figure(
            data=[
                go.Table(
                    header={
                        "values": list(
                            dataframe.columns
                        )
                    },
                    cells={
                        "values": [
                            dataframe[column]
                            for column
                            in dataframe.columns
                        ]
                    },
                )
            ]
        )

        figure.update_layout(
            title=spec.title
        )

    else:
        raise ValueError(
            "Unsupported visualization type: "
            f"{spec.chart_type.value}"
        )

    figure.update_layout(
        xaxis_title=spec.x_axis_title,
        yaxis_title=spec.y_axis_title,
    )

    return figure