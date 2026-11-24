from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import (
    ClientSession,
    StdioServerParameters,
)
from mcp.client.stdio import (
    stdio_client,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


class AnalyticsMCPClient:
    """
    Application-level client for the local Northwind
    Analytics MCP server.

    A new stdio session is created for each public call.
    This is simple and reliable for the first integration.
    A persistent session can be added later if latency
    becomes material.
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.timeout_seconds = (
            timeout_seconds
        )

    @staticmethod
    def _server_parameters(
    ) -> StdioServerParameters:
        """
        Start the MCP server with the same Python
        interpreter and virtual environment as the client.
        """

        return StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                (
                    "mcp_servers."
                    "analytics_server"
                ),
            ],
            cwd=str(
                PROJECT_ROOT
            ),
        )

    @staticmethod
    def _extract_tool_data(
        result: object,
    ) -> dict:
        """
        Extract a dictionary returned by an MCP tool.

        Structured content is preferred. Text content is
        parsed as JSON when possible and preserved as an
        error message otherwise.
        """

        structured_content = getattr(
            result,
            "structuredContent",
            None,
        )

        if structured_content is None:
            structured_content = getattr(
                result,
                "structured_content",
                None,
            )

        if isinstance(
            structured_content,
            dict,
        ):
            # Compatibility with SDKs that wrap the tool
            # response under a "result" key.
            wrapped_result = (
                structured_content.get(
                    "result"
                )
            )

            if (
                len(structured_content) == 1
                and isinstance(
                    wrapped_result,
                    dict,
                )
            ):
                return wrapped_result

            return structured_content

        content_items = getattr(
            result,
            "content",
            [],
        )

        text_messages: list[str] = []

        for item in content_items:
            text = getattr(
                item,
                "text",
                None,
            )

            if not isinstance(
                text,
                str,
            ):
                continue

            stripped_text = text.strip()

            if not stripped_text:
                continue

            text_messages.append(
                stripped_text
            )

            try:
                parsed = json.loads(
                    stripped_text
                )

            except json.JSONDecodeError:
                continue

            if isinstance(
                parsed,
                dict,
            ):
                wrapped_result = (
                    parsed.get(
                        "result"
                    )
                )

                if (
                    len(parsed) == 1
                    and isinstance(
                        wrapped_result,
                        dict,
                    )
                ):
                    return wrapped_result

                return parsed

        is_error = bool(
            getattr(
                result,
                "isError",
                False,
            )
            or getattr(
                result,
                "is_error",
                False,
            )
        )

        if text_messages:
            return {
                "success": False,
                "data": None,
                "errors": text_messages,
                "warnings": [],
                "is_error": is_error,
            }

        return {
            "success": False,
            "data": None,
            "errors": [
                (
                    "The MCP tool did not return "
                    "structured dictionary content."
                )
            ],
            "warnings": [],
            "is_error": is_error,
        }

    async def _call_tool_async(
        self,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """
        Open a stdio MCP session, call one tool, and close
        the server subprocess cleanly.
        """

        server_parameters = (
            self._server_parameters()
        )

        async def invoke() -> dict:
            async with stdio_client(
                server_parameters
            ) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:
                    await session.initialize()

                    result = (
                        await session.call_tool(
                            tool_name,
                            arguments=arguments,
                        )
                    )

                    return (
                        self._extract_tool_data(
                            result
                        )
                    )

        try:
            return await asyncio.wait_for(
                invoke(),
                timeout=(
                    self.timeout_seconds
                ),
            )

        except TimeoutError:
            return {
                "success": False,
                "data": None,
                "errors": [
                    (
                        "The MCP tool call exceeded "
                        f"{self.timeout_seconds} "
                        "seconds."
                    )
                ],
                "warnings": [],
            }

        except Exception as error:
            return {
                "success": False,
                "data": None,
                "errors": [
                    (
                        "MCP tool call failed: "
                        f"{error}"
                    )
                ],
                "warnings": [],
            }

    def call_tool(
        self,
        tool_name: str,
        arguments: dict | None = None,
    ) -> dict:
        """
        Synchronous entry point for Streamlit, agents, and
        LangGraph nodes.

        Call this only from synchronous application code.
        """

        try:
            asyncio.get_running_loop()

        except RuntimeError:
            return asyncio.run(
                self._call_tool_async(
                    tool_name=tool_name,
                    arguments=(
                        arguments or {}
                    ),
                )
            )

        raise RuntimeError(
            "AnalyticsMCPClient.call_tool() cannot "
            "run inside an active event loop. Use "
            "_call_tool_async() from asynchronous code."
        )

    async def list_tools_async(
        self,
    ) -> list[str]:
        """
        Discover MCP tools exposed by the server.
        """

        server_parameters = (
            self._server_parameters()
        )

        async with stdio_client(
            server_parameters
        ) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()

                response = (
                    await session.list_tools()
                )

                return [
                    tool.name
                    for tool in response.tools
                ]

    def list_tools(
        self,
    ) -> list[str]:
        return asyncio.run(
            self.list_tools_async()
        )

    def list_capabilities(
        self,
    ) -> dict:
        return self.call_tool(
            "list_capabilities",
            {},
        )

    def get_metric_definition(
        self,
        metric_name: str,
    ) -> dict:
        return self.call_tool(
            "get_metric_definition",
            {
                "metric_name": (
                    metric_name
                )
            },
        )

    def get_dimension_definition(
        self,
        dimension_name: str,
    ) -> dict:
        return self.call_tool(
            "get_dimension_definition",
            {
                "dimension_name": (
                    dimension_name
                )
            },
        )

    def compile_query(
        self,
        query_spec: dict,
        task_id: str = "T1",
    ) -> dict:
        return self.call_tool(
            "compile_analytical_query",
            {
                "query_spec": (
                    query_spec
                ),
                "task_id": task_id,
            },
        )

    def validate_sql(
        self,
        sql: str,
    ) -> dict:
        return self.call_tool(
            "validate_read_only_sql",
            {
                "sql": sql,
            },
        )

    def execute_query(
        self,
        sql: str,
        parameters: (
            dict | None
        ) = None,
    ) -> dict:
        """
        Execute one validated, read-only SQL query through
        the MCP analytics server.
        """

        return self.call_tool(
            "execute_validated_query",
            {
                "sql": sql,
                "parameters": (
                    parameters or {}
                ),
            },
        )

    def rank_rows(
        self,
        rows: list[dict],
        label_column: str,
        value_column: str,
        descending: bool = True,
        limit: int | None = None,
    ) -> dict:
        return self.call_tool(
            "rank_records",
            {
                "rows": rows,
                "label_column": (
                    label_column
                ),
                "value_column": (
                    value_column
                ),
                "descending": (
                    descending
                ),
                "limit": limit,
            },
        )