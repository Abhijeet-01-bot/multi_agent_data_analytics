from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class VisualizationType(str, Enum):
    KPI = "kpi"
    TABLE = "table"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    STACKED_BAR = "stacked_bar"
    WATERFALL = "waterfall"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    HEATMAP = "heatmap"


class SortOrder(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class VisualizationSpec(BaseModel):
    """
    Structured chart specification proposed by the
    Reporting Agent and rendered by deterministic code.
    """

    visualization_id: str

    chart_type: VisualizationType

    title: str

    description: str

    evidence_id: str

    x_field: str | None = None
    y_field: str | None = None

    category_field: str | None = None
    series_field: str | None = None

    value_field: str | None = None
    label_field: str | None = None

    sort_order: SortOrder | None = None

    top_n: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    x_axis_title: str | None = None
    y_axis_title: str | None = None

    show_values: bool = False

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_required_fields(
        self,
    ) -> "VisualizationSpec":
        if self.chart_type in {
            VisualizationType.BAR,
            VisualizationType.HORIZONTAL_BAR,
            VisualizationType.LINE,
            VisualizationType.STACKED_BAR,
            VisualizationType.SCATTER,
        }:
            if not self.x_field or not self.y_field:
                raise ValueError(
                    f"{self.chart_type.value} charts "
                    "require x_field and y_field."
                )

        if self.chart_type == VisualizationType.KPI:
            if not self.value_field:
                raise ValueError(
                    "KPI visualizations require "
                    "value_field."
                )

        if self.chart_type == VisualizationType.HISTOGRAM:
            if not self.x_field:
                raise ValueError(
                    "Histogram visualizations require "
                    "x_field."
                )

        if self.chart_type == VisualizationType.BOX:
            if not self.y_field:
                raise ValueError(
                    "Box visualizations require "
                    "y_field."
                )

        if self.chart_type == VisualizationType.WATERFALL:
            if not self.x_field or not self.y_field:
                raise ValueError(
                    "Waterfall visualizations require "
                    "x_field and y_field."
                )

        return self


class VisualizationValidationResult(BaseModel):
    is_valid: bool

    visualization_id: str

    available_fields: list[str] = Field(
        default_factory=list
    )

    missing_fields: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )