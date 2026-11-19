from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    QUERY_RESULT = "query_result"
    VALIDATION_RESULT = "validation_result"
    CALCULATION = "calculation"
    STATISTICAL_RESULT = "statistical_result"
    DATA_LIMITATION = "data_limitation"


class EvidenceRecord(BaseModel):
    """
    One traceable piece of evidence produced by the
    database or deterministic Python tools.
    """

    evidence_id: str

    task_id: str

    evidence_type: EvidenceType

    title: str

    description: str

    source_sql: str | None = None

    source_parameters: dict[str, Any] = Field(
        default_factory=dict
    )

    source_columns: list[str] = Field(
        default_factory=list
    )

    source_rows: list[dict[str, Any]] = Field(
        default_factory=list
    )

    calculation_name: str | None = None

    calculation_inputs: dict[str, Any] = Field(
        default_factory=dict
    )

    calculation_output: dict[str, Any] = Field(
        default_factory=dict
    )

    validated: bool = False

    warnings: list[str] = Field(
        default_factory=list
    )


class EvidenceBundle(BaseModel):
    """
    Collection of evidence associated with one
    analytical request.
    """

    request_id: str

    records: list[EvidenceRecord] = Field(
        default_factory=list
    )

    record_count: int = 0

    validated_record_count: int = 0

    warnings: list[str] = Field(
        default_factory=list
    )