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
from schemas.intent_schemas import IntentResult
from schemas.planning_schemas import (
    AnalyticalTask,
    ExecutionPlan,
)
from schemas.sql_generation_schemas import (
    GeneratedSQLQuery,
    SQLCorrectionContext,
    SQLTaskResult,
)
from tools.query_executor import execute_read_only_query
from tools.sql_generation_context import build_sql_generation_context
from tools.sql_validator import validate_sql
from tools.sql_identifier_normalizer import (
    normalize_sql_identifiers,
    normalize_table_names,
)


class StructuredSQLModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> GeneratedSQLQuery:
        ...


class SQLGenerationAgent:
    """
    Generate, validate, correct and execute parameterized
    SQL for one analytical task.
    """

    def __init__(
        self,
        structured_model: StructuredSQLModel | None = None,
    ) -> None:
        if structured_model is None:
            llm = create_llm()
            structured_model = llm.with_structured_output(
                GeneratedSQLQuery,
                method="json_schema",
            )

        self.structured_model = structured_model

    def _generate_candidate(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        task: AnalyticalTask,
        correction: SQLCorrectionContext | None = None,
    ) -> GeneratedSQLQuery:
        sql_context = build_sql_generation_context(
            intent=intent,
            plan=plan,
            task=task,
        )

        prompt = build_sql_user_prompt(
            intent=intent,
            plan=plan,
            task=task,
            sql_context=sql_context,
            correction=correction,
        )

        messages = [
            SystemMessage(content=SQL_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        raw_result = self.structured_model.invoke(
            messages
        )

        if isinstance(
            raw_result,
            GeneratedSQLQuery,
        ):
            candidate_data = raw_result.model_dump(
                mode="json"
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
            candidate_data = raw_result.model_dump(
                mode="json"
            )

        else:
            raise TypeError(
                "The SQL Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        # task_id is workflow metadata selected by the
        # Planning Agent. The LLM must not control or
        # replace it.
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

        assumptions.extend(corrections)

        candidate_data[
            "assumptions"
        ] = assumptions
        result = GeneratedSQLQuery.model_validate(
            candidate_data
        )
        candidate_data[
            "referenced_tables"
        ] = normalize_table_names(
            candidate_data.get(
                "referenced_tables",
                [],
            )
            or []
        )

        return result
    @staticmethod
    def _build_deterministic_query(
        intent: IntentResult,
        task: AnalyticalTask,
    ) -> GeneratedSQLQuery | None:
        """
        Build SQL deterministically for supported,
        unambiguous analytical patterns.

        More complex tasks return None and continue through
        the LLM SQL-generation path.
        """

        metrics = set(intent.metrics)
        dimensions = set(intent.dimensions)

        filters = {
            intent_filter.field: (
                intent_filter.value
            )
            for intent_filter in intent.filters
        }

        # Total order count.
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
                referenced_tables=["Orders"],
                expected_columns=[
                    expected_alias
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

        # Top categories by net revenue for a shipping
        # country.
        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and "ship_country" in filters
        ):
            country = filters[
                "ship_country"
            ]

            limit = intent.limit or 100
            safe_limit = max(
                1,
                min(int(limit), 100),
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
                    "by product category for orders "
                    f"shipped to {country}, then returns "
                    f"the top {safe_limit} categories."
                ),
                assumptions=[
                    (
                        "Germany refers to the order "
                        "shipping destination."
                    )
                ],
            )
                # Total net revenue filtered by shipping country.
        #
        # HAVING COUNT(*) > 0 ensures that an unmatched
        # filter produces zero rows rather than one row
        # containing a NULL aggregate.
        if (
            metrics == {"net_revenue"}
            and not dimensions
            and set(filters.keys())
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
                    expected_alias
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
        # Total net revenue.
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
                    "Order Details"
                ],
                expected_columns=[
                    expected_alias
                ],
                explanation=(
                    "Calculates total net revenue using "
                    "the approved line-item formula."
                ),
                assumptions=[],
            )
                # Category net-revenue ranking without filters.
        #
        # Example:
        # "Show the top five categories by revenue."
        if (
            metrics == {"net_revenue"}
            and dimensions == {"category"}
            and not filters
        ):
            safe_limit = max(
                1,
                min(
                    int(intent.limit or 5),
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
                    "for each product category and "
                    f"returns the top {safe_limit} "
                    "categories."
                ),
                assumptions=[
                    (
                        "Revenue means net revenue after "
                        "applying the order-line discount."
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
        Generate and execute SQL with deterministic
        templates for known simple metrics and a bounded
        LLM correction loop for complex tasks.
        """

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
                    query=deterministic_query,
                    validation=validation,
                    execution=None,
                    correction_history=[],
                    errors=validation.errors,
                )

            execution = execute_read_only_query(
                sql=deterministic_query.sql,
                parameters=(
                    deterministic_query.parameters
                ),
            )

            if not execution.success:
                return SQLTaskResult(
                    success=False,
                    task_id=task.task_id,
                    attempts=1,
                    query=deterministic_query,
                    validation=validation,
                    execution=execution,
                    correction_history=[],
                    errors=execution.errors,
                )

            return SQLTaskResult(
                success=True,
                task_id=task.task_id,
                attempts=1,
                query=deterministic_query,
                validation=validation,
                execution=execution,
                correction_history=[],
                errors=[],
            )

        # Complex tasks continue through the existing
        # LLM-based generation and correction process.
        correction_history: list[
            SQLCorrectionContext
        ] = []

        correction: (
            SQLCorrectionContext | None
        ) = None

        maximum_attempts = (
            settings.max_sql_retries + 1
        )

        last_query: (
            GeneratedSQLQuery | None
        ) = None

        last_validation = None
        last_execution = None

        for attempt in range(
            1,
            maximum_attempts + 1,
        ):
            candidate = self._generate_candidate(
                intent=intent,
                plan=plan,
                task=task,
                correction=correction,
            )

            last_query = candidate

            validation = validate_sql(
                candidate.sql
            )

            last_validation = validation

            if not validation.is_valid:
                correction = SQLCorrectionContext(
                    attempt_number=attempt,
                    previous_sql=candidate.sql,
                    previous_parameters=(
                        candidate.parameters
                    ),
                    validation_errors=(
                        validation.errors
                    ),
                    execution_errors=[],
                )

                correction_history.append(
                    correction
                )

                continue

            execution = execute_read_only_query(
                sql=candidate.sql,
                parameters=(
                    candidate.parameters
                ),
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
                )

            correction = SQLCorrectionContext(
                attempt_number=attempt,
                previous_sql=candidate.sql,
                previous_parameters=(
                    candidate.parameters
                ),
                validation_errors=[],
                execution_errors=(
                    execution.errors
                ),
            )

            correction_history.append(
                correction
            )

        final_errors: list[str] = []

        if last_validation is not None:
            final_errors.extend(
                last_validation.errors
            )

        if last_execution is not None:
            final_errors.extend(
                last_execution.errors
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
            errors=final_errors,
        )
