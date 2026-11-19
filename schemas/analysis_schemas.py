from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class FindingType(str, Enum):
    OBSERVATION = "observation"
    DRIVER = "driver"
    ASSOCIATION = "association"
    HYPOTHESIS = "hypothesis"
    LIMITATION = "limitation"
    CONFIRMED_CAUSE = "confirmed_cause"


class FindingImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalyticalFinding(BaseModel):
    """
    One evidence-grounded business finding.
    """

    finding_id: str

    finding_type: FindingType

    title: str

    description: str

    importance: FindingImportance

    evidence_ids: list[str] = Field(
        min_length=1
    )

    metric: str | None = None

    dimension: str | None = None

    value: float | None = None

    unit: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    caveat: str | None = None


class AdditionalAnalysisTask(BaseModel):
    """
    A targeted analytical task requested when current
    evidence is insufficient.
    """

    description: str

    reason: str

    metrics: list[str] = Field(
        default_factory=list
    )

    dimensions: list[str] = Field(
        default_factory=list
    )

    expected_columns: list[str] = Field(
        default_factory=list
    )

    priority: int = Field(
        default=1,
        ge=1,
        le=5,
    )


class AnalysisResult(BaseModel):
    """
    Structured output from the Analysis Agent.
    """

    analysis_summary: str

    findings: list[AnalyticalFinding] = Field(
        default_factory=list
    )

    evidence_sufficient: bool

    unanswered_questions: list[str] = Field(
        default_factory=list
    )

    additional_tasks: list[
        AdditionalAnalysisTask
    ] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(
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
    def validate_analysis(
        self,
    ) -> "AnalysisResult":
        if (
            not self.evidence_sufficient
            and not self.additional_tasks
            and not self.unanswered_questions
        ):
            raise ValueError(
                "Insufficient evidence must include "
                "an unanswered question or an "
                "additional analytical task."
            )

        finding_ids = [
            finding.finding_id
            for finding in self.findings
        ]

        if len(finding_ids) != len(
            set(finding_ids)
        ):
            raise ValueError(
                "Every finding must have a unique "
                "finding_id."
            )

        return self