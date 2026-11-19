from enum import Enum

from pydantic import BaseModel, Field


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    NEEDS_CLARIFICATION = (
        "needs_clarification"
    )
    UNSUPPORTED_ANALYSIS = (
        "unsupported_analysis"
    )
    UNSUPPORTED_DATA = (
        "unsupported_data"
    )


class CapabilityAssessment(BaseModel):
    support_status: SupportStatus

    reason: str

    required_metrics: list[str] = Field(
        default_factory=list
    )

    required_dimensions: list[str] = Field(
        default_factory=list
    )

    required_operations: list[str] = Field(
        default_factory=list
    )

    missing_metrics: list[str] = Field(
        default_factory=list
    )

    missing_dimensions: list[str] = Field(
        default_factory=list
    )

    unsupported_operations: list[str] = Field(
        default_factory=list
    )

    suggested_questions: list[str] = Field(
        default_factory=list
    )