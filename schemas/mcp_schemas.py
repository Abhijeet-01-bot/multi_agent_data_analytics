from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MCPToolResponse(BaseModel):
    success: bool

    data: Any = None

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class CompileQueryRequest(BaseModel):
    query_spec: dict[str, Any]
    task_id: str = "T1"


class ExecuteQueryRequest(BaseModel):
    sql: str
    parameters: dict[str, Any] = Field(
        default_factory=dict
    )


class RankingRequest(BaseModel):
    rows: list[dict[str, Any]]
    label_column: str
    value_column: str
    descending: bool = True
    limit: int | None = None
