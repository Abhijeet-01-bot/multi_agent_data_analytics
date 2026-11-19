from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class TaskType(str, Enum):
    DATA_RETRIEVAL = "data_retrieval"
    AGGREGATION = "aggregation"
    FILTERING = "filtering"
    RANKING = "ranking"
    COMPARISON = "comparison"
    TREND_ANALYSIS = "trend_analysis"
    CONTRIBUTION_ANALYSIS = "contribution_analysis"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    DATA_VALIDATION = "data_validation"


class ChartType(str, Enum):
    KPI_CARD = "kpi_card"
    TABLE = "table"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    STACKED_BAR = "stacked_bar"
    WATERFALL = "waterfall"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    HEATMAP = "heatmap"


class PlanFilter(BaseModel):
    field: str

    operator: str = "equals"

    value: Any


class RequiredJoin(BaseModel):
    left_table: str
    left_column: str

    right_table: str
    right_column: str

    join_type: str = Field(
        default="inner",
        description=(
            "Join type such as inner, left, right, "
            "or full."
        ),
    )

    reason: str = Field(
        default="",
        description=(
            "Reason this join is needed for the task."
        ),
    )


class AnalyticalTask(BaseModel):
    task_id: str = Field(
        description=(
            "Unique task identifier such as T1 or T2."
        )
    )

    description: str

    task_type: TaskType

    metrics: list[str] = Field(
        default_factory=list
    )

    dimensions: list[str] = Field(
        default_factory=list
    )

    filters: list[PlanFilter] = Field(
        default_factory=list
    )

    required_tables: list[str] = Field(
        default_factory=list
    )

    expected_columns: list[str] = Field(
        default_factory=list
    )

    depends_on: list[str] = Field(
        default_factory=list
    )

    execution_notes: list[str] = Field(
        default_factory=list
    )


class ChartRecommendation(BaseModel):
    chart_type: ChartType

    title: str

    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None

    reason: str


class ExecutionPlan(BaseModel):
    plan_summary: str

    tasks: list[AnalyticalTask] = Field(
        min_length=1
    )

    required_tables: list[str] = Field(
        default_factory=list
    )

    required_joins: list[RequiredJoin] = Field(
        default_factory=list
    )

    chart_recommendations: list[
        ChartRecommendation
    ] = Field(
        default_factory=list
    )

    completion_criteria: list[str] = Field(
        default_factory=list
    )

    assumptions: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    requires_additional_data: bool = False

    additional_data_reason: str | None = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_plan(self) -> "ExecutionPlan":
        task_ids = [
            task.task_id
            for task in self.tasks
        ]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError(
                "Every planning task must have a "
                "unique task_id."
            )

        known_task_ids = set(task_ids)

        for task in self.tasks:
            for dependency in task.depends_on:
                if dependency not in known_task_ids:
                    raise ValueError(
                        f"Task {task.task_id} depends on "
                        f"unknown task {dependency}."
                    )

                if dependency == task.task_id:
                    raise ValueError(
                        f"Task {task.task_id} cannot "
                        "depend on itself."
                    )

        if (
            self.requires_additional_data
            and not self.additional_data_reason
        ):
            raise ValueError(
                "additional_data_reason is required "
                "when requires_additional_data is true."
            )

        return self