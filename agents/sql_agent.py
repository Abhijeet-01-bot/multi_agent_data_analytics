from __future__ import annotations

from typing import Protocol

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from config.llm import create_llm
from config.settings import settings
from prompts.sql_prompt import (
    SQL_SYSTEM_PROMPT,
    build_sql_user_prompt,
)
from schemas.intent_schemas import (
    IntentResult,
)
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
)
from schemas.sql_generation_schemas import (
    GeneratedSQLQuery,
    SQLCorrectionContext,
    SQLTaskResult,
)
from schemas.sql_schemas import (
    QueryExecutionResult,
    SQLValidationResult,
)
from semantic.query_spec_builder import (
    build_query_spec,
)
from services.analytics_gateway import (
    AnalyticsGateway,
)
from tools.query_executor import (
    execute_read_only_query,
)
from tools.sql_generation_context import (
    build_sql_generation_context,
)
from tools.sql_identifier_normalizer import (
    normalize_sql_identifiers,
    normalize_table_names,
)
from tools.sql_validator import (
    validate_sql,
)


class StructuredSQLModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> GeneratedSQLQuery:
        ...


class SQLGenerationAgent:
    """
    Generate, validate, correct, and execute parameterized
    SQL for one analytical task.

    Execution priority:

    1. Generic QuerySpec through AnalyticsGateway.
    2. Existing deterministic SQL templates.
    3. Bounded LLM SQL generation and correction.

    AnalyticsGateway uses MCP when MCP is enabled and
    direct in-process services otherwise.
    """

    def __init__(
        self,
        structured_model: (
            StructuredSQLModel | None
        ) = None,
    ) -> None:
        if structured_model is None:
            llm = create_llm()

            structured_model = (
                llm.with_structured_output(
                    GeneratedSQLQuery,
                    method="json_schema",
                )
            )

        self.structured_model = (
            structured_model
        )

        self.analytics_gateway = (
            AnalyticsGateway()
        )

    @staticmethod
    def _deduplicate_messages(
        messages: list[str],
    ) -> list[str]:
        """
        Remove duplicate messages while preserving their
        original order.
        """

        return list(
            dict.fromkeys(
                message
                for message in messages
                if message
            )
        )

    def _generate_candidate(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        task: AnalyticalTask,
        correction: (
            SQLCorrectionContext | None
        ) = None,
    ) -> GeneratedSQLQuery:
        """
        Generate one SQL candidate through the configured
        structured model.

        This path is used only when the generic compiler
        and deterministic templates cannot support the
        requested analytical pattern.
        """

        sql_context = (
            build_sql_generation_context(
                intent=intent,
                plan=plan,
                task=task,
            )
        )

        prompt = build_sql_user_prompt(
            intent=intent,
            plan=plan,
            task=task,
            sql_context=sql_context,
            correction=correction,
        )

        messages = [
            SystemMessage(
                content=SQL_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=prompt
            ),
        ]

        raw_result = (
            self.structured_model.invoke(
                messages
            )
        )

        if isinstance(
            raw_result,
            GeneratedSQLQuery,
        ):
            candidate_data = (
                raw_result.model_dump(
                    mode="json"
                )
            )

        elif isinstance(
            raw_result,
            dict,
        ):
            candidate_data = dict(
                raw_result
            )

        elif hasattr(
            raw_result,
            "model_dump",
        ):
            candidate_data = (
                raw_result.model_dump(
                    mode="json"
                )
            )

        else:
            raise TypeError(
                "The SQL Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        # The selected task ID is authoritative workflow
        # metadata. The model must not replace it.
        candidate_data["task_id"] = (
            task.task_id
        )

        candidate_data.setdefault(
            "parameters",
            {},
        )

        candidate_data.setdefault(
            "referenced_tables",
            [],
        )

        candidate_data.setdefault(
            "expected_columns",
            task.expected_columns,
        )

        candidate_data.setdefault(
            "explanation",
            (
                "Parameterized SQL generated for "
                f"task {task.task_id}."
            ),
        )

        candidate_data.setdefault(
            "assumptions",
            [],
        )

        raw_sql = str(
            candidate_data.get(
                "sql",
                "",
            )
        )

        normalized_sql, corrections = (
            normalize_sql_identifiers(
                raw_sql
            )
        )

        candidate_data["sql"] = (
            normalized_sql
        )

        assumptions = list(
            candidate_data.get(
                "assumptions",
                [],
            )
            or []
        )

        assumptions.extend(
            corrections
        )

        candidate_data[
            "assumptions"
        ] = assumptions

        # Normalize referenced table names before model
        # validation. The previous implementation validated
        # first, so normalized names were never returned.
        candidate_data[
            "referenced_tables"
        ] = normalize_table_names(
            candidate_data.get(
                "referenced_tables",
                [],
            )
            or []
        )

        return (
            GeneratedSQLQuery
            .model_validate(
                candidate_data
            )
        )

    @staticmethod
    def _build_deterministic_query(
        intent: IntentResult,
        task: AnalyticalTask,
    ) -> GeneratedSQLQuery | None:
        """
        Build SQL deterministically for known analytical
        patterns.

        These templates remain available behind the
        generic QuerySpec compiler as a reliable fallback.
        """

        metrics = set(
            intent.metrics
        )

        dimensions = set(
            intent.dimensions
        )

        filters = {
            intent_filter.field: (
                intent_filter.value
            )
            for intent_filter
            in intent.filters
        }

        # -------------------------------------------------
        # Total order count
        # -------------------------------------------------

        if (
            metrics == {"order_count"}
            and not dimensions
            and not filters
        ):
            expected_alias = (
                task.expected_columns[0]
                if task.expected_columns
                else "OrderCount"
            )

            return GeneratedSQLQuery(
                task_id=task.task_id,
                sql=(
                    "SELECT\n"
                    "    COUNT(DISTINCT OrderID) "
                    f'AS "{expected_alias}"\n'
                    "FROM Orders"
                ),
                parameters={},
                referenced_tables=[
                    "Orders",
                ],
                expected_columns=[
                    expected_alias,
                ],
                explanation=(
                    "Counts unique orders directly "
                    "from the Orders table."
                ),
                assumptions=[
                    (
                        "Each unique OrderID represents "
                        "one order."
                    )
                ],
            )

        # -------------------------------------------------
        # Top categories by net revenue for one shipping
        # country
        # -------------------------------------------------

        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and set(
                filters.keys()
            )
            == {"ship_country"}
        ):
            country = filters[
                "ship_country"
            ]

            safe_limit = max(
                1,
                min(
                    int(
                        intent.limit or 100
                    ),
                    100,
                ),
            )

            sql = (
                "SELECT\n"
                "    c.CategoryName "
                'AS "CategoryName",\n'
                "    ROUND(\n"
                "        SUM(\n"
                "            od.UnitPrice\n"
                "            * od.Quantity\n"
                "            * (1 - od.Discount)\n"
                "        ),\n"
                "        2\n"
                '    ) AS "NetRevenue"\n'
                "FROM Orders AS o\n"
                'JOIN "Order Details" AS od\n'
                "    ON o.OrderID = od.OrderID\n"
                "JOIN Products AS p\n"
                "    ON od.ProductID = p.ProductID\n"
                "JOIN Categories AS c\n"
                "    ON p.CategoryID = c.CategoryID\n"
                "WHERE o.ShipCountry = "
                ":ship_country\n"
                "GROUP BY\n"
                "    c.CategoryID,\n"
                "    c.CategoryName\n"
                "ORDER BY\n"
                "    NetRevenue DESC\n"
                f"LIMIT {safe_limit}"
            )

            return GeneratedSQLQuery(
                task_id=task.task_id,
                sql=sql,
                parameters={
                    "ship_country": country,
                },
                referenced_tables=[
                    "Orders",
                    "Order Details",
                    "Products",
                    "Categories",
                ],
                expected_columns=[
                    "CategoryName",
                    "NetRevenue",
                ],
                explanation=(
                    "Calculates discounted net revenue "
                    "by category for orders shipped to "
                    f"{country}, then returns the top "
                    f"{safe_limit} categories."
                ),
                assumptions=[
                    (
                        "The supplied country refers "
                        "to Orders.ShipCountry."
                    )
                ],
            )

        # -------------------------------------------------
        # Total net revenue filtered by shipping country
        # -------------------------------------------------
        #
        # HAVING COUNT(*) > 0 converts the NULL aggregate
        # returned for no matches into zero rows, allowing
        # the graph to route to its no_data node.

        if (
            metrics == {"net_revenue"}
            and not dimensions
            and set(
                filters.keys()
            )
            == {"ship_country"}
        ):
            country = filters[
                "ship_country"
            ]

            expected_alias = (
                task.expected_columns[0]
                if task.expected_columns
                else "NetRevenue"
            )

            sql = (
                "SELECT\n"
                "    ROUND(\n"
                "        SUM(\n"
                "            od.UnitPrice\n"
                "            * od.Quantity\n"
                "            * (1 - od.Discount)\n"
                "        ),\n"
                "        2\n"
                "    ) "
                f'AS "{expected_alias}"\n'
                                "FROM Orders AS o\n"
                'JOIN "Order Details" AS od\n'
                "    ON o.OrderID = od.OrderID\n"
                "WHERE o.ShipCountry = "
                ":ship_country\n"
                "HAVING COUNT(*) > 0"
            )

            return GeneratedSQLQuery(
                task_id=task.task_id,
                sql=sql,
                parameters={
                    "ship_country": country,
                },
                referenced_tables=[
                    "Orders",
                    "Order Details",
                ],
                expected_columns=[
                    expected_alias,
                ],
                explanation=(
                    "Calculates total discounted net "
                    "revenue for orders shipped to the "
                    "requested country."
                ),
                assumptions=[
                    (
                        "The supplied country refers "
                        "to Orders.ShipCountry."
                    )
                ],
            )

        # -------------------------------------------------
        # Total net revenue
        # -------------------------------------------------

        if (
            metrics == {"net_revenue"}
            and not dimensions
            and not filters
        ):
            expected_alias = (
                task.expected_columns[0]
                if task.expected_columns
                else "NetRevenue"
            )

            return GeneratedSQLQuery(
                task_id=task.task_id,
                sql=(
                    "SELECT\n"
                    "    ROUND(\n"
                    "        SUM(\n"
                    "            UnitPrice\n"
                    "            * Quantity\n"
                    "            * (1 - Discount)\n"
                    "        ),\n"
                    "        2\n"
                    "    ) "
                    f'AS "{expected_alias}"\n'
                    'FROM "Order Details"'
                ),
                parameters={},
                referenced_tables=[
                    "Order Details",
                ],
                expected_columns=[
                    expected_alias,
                ],
                explanation=(
                    "Calculates total net revenue using "
                    "the approved line-item formula."
                ),
                assumptions=[],
            )

        # -------------------------------------------------
        # Category net-revenue ranking without filters
        # -------------------------------------------------

        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and not filters
        ):
            safe_limit = max(
                1,
                min(
                    int(
                        intent.limit or 5
                    ),
                    100,
                ),
            )

            sql = (
                "SELECT\n"
                "    c.CategoryName "
                'AS "CategoryName",\n'
                "    ROUND(\n"
                "        SUM(\n"
                "            od.UnitPrice\n"
                "            * od.Quantity\n"
                "            * (1 - od.Discount)\n"
                "        ),\n"
                "        2\n"
                '    ) AS "NetRevenue"\n'
                'FROM "Order Details" AS od\n'
                "JOIN Products AS p\n"
                "    ON od.ProductID = p.ProductID\n"
                "JOIN Categories AS c\n"
                "    ON p.CategoryID = c.CategoryID\n"
                "GROUP BY\n"
                "    c.CategoryID,\n"
                "    c.CategoryName\n"
                "ORDER BY\n"
                "    NetRevenue DESC\n"
                f"LIMIT {safe_limit}"
            )

            return GeneratedSQLQuery(
                task_id=task.task_id,
                sql=sql,
                parameters={},
                referenced_tables=[
                    "Order Details",
                    "Products",
                    "Categories",
                ],
                expected_columns=[
                    "CategoryName",
                    "NetRevenue",
                ],
                explanation=(
                    "Calculates discounted net revenue "
                    "for each category and returns the "
                    f"top {safe_limit} categories."
                ),
                assumptions=[
                    (
                        "Revenue means net revenue after "
                        "applying the order-line "
                        "discount."
                    )
                ],
            )

        return None

    def run_task(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        task: AnalyticalTask,
    ) -> SQLTaskResult:
        """
        Compile, validate, and execute SQL through the
        gateway, deterministic templates, or the bounded
        LLM correction path.
        """

        # =================================================
        # 1. Generic QuerySpec through AnalyticsGateway
        # =================================================

        compiled_query: (
            GeneratedSQLQuery | None
        ) = None

        compile_warnings: list[str] = []

        try:
            query_spec = build_query_spec(
                intent
            )

            compiled_response = (
                self.analytics_gateway
                .compile_query(
                    query_spec=(
                        query_spec.model_dump(
                            mode="json"
                        )
                    ),
                    task_id=task.task_id,
                )
            )

            compile_warnings.extend(
                compiled_response.get(
                    "warnings",
                    [],
                )
                or []
            )

            compile_backend = (
                compiled_response.get(
                    "backend"
                )
            )

            if compile_backend:
                compile_warnings.append(
                    (
                        "Query compilation backend: "
                        f"{compile_backend}."
                    )
                )

            compile_warnings = (
                self._deduplicate_messages(
                    compile_warnings
                )
            )

            if compiled_response.get(
                "success",
                False,
            ):
                response_data = (
                    compiled_response.get(
                        "data"
                    )
                    or {}
                )

                query_data = (
                    response_data.get(
                        "query"
                    )
                    or {}
                )

                compiled_query = (
                    GeneratedSQLQuery
                    .model_validate(
                        query_data
                    )
                )

        except (
            ValueError,
            TypeError,
            KeyError,
        ):
            compiled_query = None

        except Exception:
            # An MCP or gateway failure must not crash the
            # workflow while fallback paths are available.
            compiled_query = None

        if compiled_query is not None:
            validation = validate_sql(
                compiled_query.sql
            )

            if not validation.is_valid:
                warnings = (
                    self._deduplicate_messages(
                        [
                            *compile_warnings,
                            *list(
                                validation.warnings
                                or []
                            ),
                        ]
                    )
                )

                return SQLTaskResult(
                    success=False,
                    task_id=task.task_id,
                    attempts=1,
                    query=compiled_query,
                    validation=validation,
                    execution=None,
                    correction_history=[],
                    errors=list(
                        validation.errors
                        or []
                    ),
                    warnings=warnings,
                )

            execution_response = (
                self.analytics_gateway
                .execute_query(
                    sql=compiled_query.sql,
                    parameters=(
                        compiled_query.parameters
                    ),
                )
            )

            execution_warnings = list(
                execution_response.get(
                    "warnings",
                    [],
                )
                or []
            )

            execution_backend = (
                execution_response.get(
                    "backend"
                )
            )

            if execution_backend:
                execution_warnings.append(
                    (
                        "Query execution backend: "
                        f"{execution_backend}."
                    )
                )

            gateway_warnings = (
                self._deduplicate_messages(
                    [
                        *compile_warnings,
                        *execution_warnings,
                    ]
                )
            )

            execution_data = (
                execution_response.get(
                    "data"
                )
                or {}
            )

            # Compatibility with MCP clients that wrap the
            # service payload under a "result" key.
            if (
                isinstance(
                    execution_data,
                    dict,
                )
                and isinstance(
                    execution_data.get(
                        "result"
                    ),
                    dict,
                )
            ):
                execution_data = (
                    execution_data[
                        "result"
                    ]
                )

            if execution_response.get(
                "success",
                False,
            ):
                try:
                    execution = (
                        QueryExecutionResult
                        .model_validate(
                            execution_data
                        )
                    )

                except Exception as error:
                    execution = (
                        QueryExecutionResult(
                            success=False,
                            status=(
                                "execution_failed"
                            ),
                            sql=(
                                compiled_query.sql
                            ),
                            validation=(
                                validation
                            ),
                            errors=[
                                (
                                    "The gateway "
                                    "execution response "
                                    "could not be "
                                    "validated: "
                                    f"{error}"
                                )
                            ],
                            warnings=(
                                gateway_warnings
                            ),
                        )
                    )

            else:
                execution_errors = list(
                    execution_response.get(
                        "errors",
                        [],
                    )
                    or []
                )

                if not execution_errors:
                    execution_errors.append(
                        "The gateway query execution "
                        "failed without returning an "
                        "error message."
                    )

                execution = (
                    QueryExecutionResult(
                        success=False,
                        status=(
                            "execution_failed"
                        ),
                        columns=[],
                        rows=[],
                        returned_row_count=0,
                        truncated=False,
                        execution_time_ms=None,
                        sql=compiled_query.sql,
                        validation=validation,
                        errors=execution_errors,
                        warnings=gateway_warnings,
                    )
                )

            result_warnings = (
                self._deduplicate_messages(
                    [
                        *gateway_warnings,
                        *list(
                            execution.warnings
                            or []
                        ),
                    ]
                )
            )

            return SQLTaskResult(
                success=execution.success,
                task_id=task.task_id,
                attempts=1,
                query=compiled_query,
                validation=validation,
                execution=execution,
                correction_history=[],
                errors=(
                    []
                    if execution.success
                    else list(
                        execution.errors
                        or []
                    )
                ),
                warnings=result_warnings,
            )

        # =================================================
        # 2. Existing deterministic SQL fallback
        # =================================================

        deterministic_query = (
            self._build_deterministic_query(
                intent=intent,
                task=task,
            )
        )

        if deterministic_query is not None:
            validation = validate_sql(
                deterministic_query.sql
            )

            if not validation.is_valid:
                return SQLTaskResult(
                    success=False,
                    task_id=task.task_id,
                    attempts=1,
                    query=(
                        deterministic_query
                    ),
                    validation=validation,
                    execution=None,
                    correction_history=[],
                    errors=list(
                        validation.errors
                        or []
                    ),
                    warnings=list(
                        validation.warnings
                        or []
                    ),
                )

            execution = (
                execute_read_only_query(
                    sql=(
                        deterministic_query.sql
                    ),
                    parameters=(
                        deterministic_query
                        .parameters
                    ),
                )
            )

            return SQLTaskResult(
                success=execution.success,
                task_id=task.task_id,
                attempts=1,
                query=deterministic_query,
                validation=validation,
                execution=execution,
                correction_history=[],
                errors=(
                    []
                    if execution.success
                    else list(
                        execution.errors
                        or []
                    )
                ),
                warnings=list(
                    execution.warnings
                    or []
                ),
            )

        # =================================================
        # 3. Bounded LLM generation and correction
        # =================================================

        correction_history: list[
            SQLCorrectionContext
        ] = []

        correction: (
            SQLCorrectionContext | None
        ) = None

        maximum_attempts = (
            settings.max_sql_retries
            + 1
        )

        last_query: (
            GeneratedSQLQuery | None
        ) = None

        last_validation: (
            SQLValidationResult | None
        ) = None

        last_execution: (
            QueryExecutionResult | None
        ) = None

        for attempt in range(
            1,
            maximum_attempts + 1,
        ):
            candidate = (
                self._generate_candidate(
                    intent=intent,
                    plan=plan,
                    task=task,
                    correction=correction,
                )
            )

            last_query = candidate

            validation = validate_sql(
                candidate.sql
            )

            last_validation = validation

            if not validation.is_valid:
                correction = (
                    SQLCorrectionContext(
                        attempt_number=attempt,
                        previous_sql=(
                            candidate.sql
                        ),
                        previous_parameters=(
                            candidate.parameters
                        ),
                        validation_errors=list(
                            validation.errors
                            or []
                        ),
                        execution_errors=[],
                    )
                )

                correction_history.append(
                    correction
                )

                continue

            execution = (
                execute_read_only_query(
                    sql=candidate.sql,
                    parameters=(
                        candidate.parameters
                    ),
                )
            )

            last_execution = execution

            if execution.success:
                return SQLTaskResult(
                    success=True,
                    task_id=task.task_id,
                    attempts=attempt,
                    query=candidate,
                    validation=validation,
                    execution=execution,
                    correction_history=(
                        correction_history
                    ),
                    errors=[],
                    warnings=list(
                        execution.warnings
                        or []
                    ),
                )

            correction = (
                SQLCorrectionContext(
                    attempt_number=attempt,
                    previous_sql=(
                        candidate.sql
                    ),
                    previous_parameters=(
                        candidate.parameters
                    ),
                    validation_errors=[],
                    execution_errors=list(
                        execution.errors
                        or []
                    ),
                )
            )

            correction_history.append(
                correction
            )

        final_errors: list[str] = []
        final_warnings: list[str] = []

        if last_validation is not None:
            final_errors.extend(
                last_validation.errors
                or []
            )

            final_warnings.extend(
                last_validation.warnings
                or []
            )

        if last_execution is not None:
            final_errors.extend(
                last_execution.errors
                or []
            )

            final_warnings.extend(
                last_execution.warnings
                or []
            )

        if not final_errors:
            final_errors.append(
                "SQL generation failed after the "
                "configured retry limit."
            )

        return SQLTaskResult(
            success=False,
            task_id=task.task_id,
            attempts=maximum_attempts,
            query=last_query,
            validation=last_validation,
            execution=last_execution,
            correction_history=(
                correction_history
            ),
            errors=(
                self._deduplicate_messages(
                    final_errors
                )
            ),
            warnings=(
                self._deduplicate_messages(
                    final_warnings
                )
            ),
        )