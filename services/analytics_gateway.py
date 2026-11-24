from __future__ import annotations

from config.settings import settings
from mcp_clients.analytics_client import (
    AnalyticsMCPClient,
)
from services.mcp_analytics_service import (
    compile_query_service,
    execute_query_service,
    rank_records_service,
)


class AnalyticsGateway:
    """
    Select MCP or direct in-process execution without
    changing agent and graph contracts.
    """

    def __init__(self) -> None:
        self.mcp_client = (
            AnalyticsMCPClient(
                timeout_seconds=float(
                    settings
                    .mcp_timeout_seconds
                )
            )
        )

    @staticmethod
    def _should_fallback(
        result: dict,
    ) -> bool:
        return not result.get(
            "success",
            False,
        )

    def compile_query(
        self,
        query_spec: dict,
        task_id: str = "T1",
    ) -> dict:
        if not settings.mcp_enabled:
            return compile_query_service(
                query_spec=query_spec,
                task_id=task_id,
            )

        result = (
            self.mcp_client.compile_query(
                query_spec=query_spec,
                task_id=task_id,
            )
        )

        if (
            self._should_fallback(
                result
            )
            and settings
            .mcp_fallback_to_direct
        ):
            fallback = compile_query_service(
                query_spec=query_spec,
                task_id=task_id,
            )

            warnings = list(
                fallback.get(
                    "warnings",
                    [],
                )
            )

            warnings.append(
                "MCP compilation failed; "
                "the direct compiler was used."
            )

            fallback["warnings"] = (
                warnings
            )

            return fallback

        return result

    def execute_query(
        self,
        sql: str,
        parameters: (
            dict | None
        ) = None,
    ) -> dict:
        if not settings.mcp_enabled:
            result = execute_query_service(
                sql=sql,
                parameters=parameters,
            )

            result["backend"] = (
                "direct"
            )

            return result

        result = (
            self.mcp_client.execute_query(
                sql=sql,
                parameters=parameters,
            )
        )

        if result.get(
            "success",
            False,
        ):
            result["backend"] = "mcp"
            return result

        if (
            settings
            .mcp_fallback_to_direct
        ):
            fallback = execute_query_service(
                sql=sql,
                parameters=parameters,
            )

            fallback["backend"] = (
                "direct_fallback"
            )

            warnings = list(
                fallback.get(
                    "warnings",
                    [],
                )
                or []
            )

            warnings.append(
                "MCP execution failed; "
                "the direct executor was used."
            )

            fallback["warnings"] = (
                warnings
            )

            return fallback

        result["backend"] = "mcp"
        return result

    def rank_rows(
        self,
        rows: list[dict],
        label_column: str,
        value_column: str,
        descending: bool = True,
        limit: int | None = None,
    ) -> dict:
        if not settings.mcp_enabled:
            return rank_records_service(
                rows=rows,
                label_column=label_column,
                value_column=value_column,
                descending=descending,
                limit=limit,
            )

        result = (
            self.mcp_client.rank_rows(
                rows=rows,
                label_column=label_column,
                value_column=value_column,
                descending=descending,
                limit=limit,
            )
        )

        if (
            self._should_fallback(
                result
            )
            and settings
            .mcp_fallback_to_direct
        ):
            fallback = (
                rank_records_service(
                    rows=rows,
                    label_column=(
                        label_column
                    ),
                    value_column=(
                        value_column
                    ),
                    descending=(
                        descending
                    ),
                    limit=limit,
                )
            )

            warnings = list(
                fallback.get(
                    "warnings",
                    [],
                )
            )

            warnings.append(
                "MCP ranking failed; "
                "direct analytics was used."
            )

            fallback["warnings"] = (
                warnings
            )

            return fallback

        return result