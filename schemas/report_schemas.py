from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from schemas.visualization_schemas import (
    VisualizationSpec,
)


class RecommendationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportFinding(BaseModel):
    """
    A presentation-ready version of an analytical
    finding.
    """

    finding_id: str

    title: str

    explanation: str

    importance: str

    evidence_ids: list[str] = Field(
        min_length=1
    )


class BusinessRecommendation(BaseModel):
    recommendation_id: str

    action: str

    rationale: str

    priority: RecommendationPriority

    related_finding_ids: list[str] = Field(
        min_length=1
    )

    evidence_ids: list[str] = Field(
        min_length=1
    )

    expected_business_value: str | None = None

    limitation: str | None = None


class ExecutiveReport(BaseModel):
    report_title: str

    executive_summary: str

    findings: list[ReportFinding] = Field(
        default_factory=list
    )

    recommendations: list[
        BusinessRecommendation
    ] = Field(
        default_factory=list
    )

    visualizations: list[
        VisualizationSpec
    ] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(
        default_factory=list
    )

    methodology_summary: str

    evidence_ids_used: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_report_ids(
        self,
    ) -> "ExecutiveReport":
        finding_ids = [
            finding.finding_id
            for finding in self.findings
        ]

        if len(finding_ids) != len(
            set(finding_ids)
        ):
            raise ValueError(
                "Report finding IDs must be unique."
            )

        recommendation_ids = [
            recommendation.recommendation_id
            for recommendation
            in self.recommendations
        ]

        if len(recommendation_ids) != len(
            set(recommendation_ids)
        ):
            raise ValueError(
                "Recommendation IDs must be unique."
            )

        visualization_ids = [
            visualization.visualization_id
            for visualization
            in self.visualizations
        ]

        if len(visualization_ids) != len(
            set(visualization_ids)
        ):
            raise ValueError(
                "Visualization IDs must be unique."
            )

        return self