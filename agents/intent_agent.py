from __future__ import annotations

import re
from typing import Any, Protocol

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from config.llm import create_llm
from config.settings import settings
from prompts.intent_prompt import (
    INTENT_SYSTEM_PROMPT,
    build_intent_user_prompt,
)
from schemas.intent_schemas import (
    AnalysisType,
    IntentFilter,
    IntentResult,
    SortDirection,
)
from tools.semantic_resolver import (
    build_intent_context,
    resolve_business_term,
)


class StructuredIntentModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> Any:
        ...


class IntentUnderstandingAgent:
    """
    Convert natural-language business questions into
    validated analytical requirements.

    Local-model output is normalized using conservative
    semantic rules before being passed downstream.
    """

    def __init__(
        self,
        structured_model: (
            StructuredIntentModel | None
        ) = None,
    ) -> None:
        if structured_model is None:
            llm = create_llm()

            if (
                settings.llm_provider
                .strip()
                .lower()
                == "ollama"
            ):
                # Request a JSON dictionary first so
                # predictable local-model omissions can be
                # repaired before Pydantic validation.
                structured_model = (
                    llm.with_structured_output(
                        IntentResult.model_json_schema(),
                        method="json_schema",
                    )
                )
            else:
                structured_model = (
                    llm.with_structured_output(
                        IntentResult,
                        method="json_schema",
                    )
                )

        self.structured_model = structured_model

    def analyze(
        self,
        user_question: str,
    ) -> IntentResult:
        cleaned_question = user_question.strip()

        if not cleaned_question:
            return IntentResult(
                business_objective=(
                    "No analytical question was provided."
                ),
                metrics=[],
                dimensions=[],
                analysis_types=[],
                ambiguity_reasons=[
                    "The business question is empty."
                ],
                clarification_required=True,
                clarification_question=(
                    "What business question would you "
                    "like me to analyze?"
                ),
                confidence=1.0,
            )

        semantic_context = build_intent_context()

        user_prompt = build_intent_user_prompt(
            user_question=cleaned_question,
            semantic_context=semantic_context,
        )

        messages = [
            SystemMessage(
                content=INTENT_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]

        raw_result = self.structured_model.invoke(
            messages
        )

        if isinstance(
            raw_result,
            IntentResult,
        ):
            intent_data = raw_result.model_dump(
                mode="json"
            )

        elif isinstance(
            raw_result,
            dict,
        ):
            intent_data = dict(raw_result)

        elif hasattr(
            raw_result,
            "model_dump",
        ):
            intent_data = raw_result.model_dump(
                mode="json"
            )

        else:
            raise TypeError(
                "The Intent Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        normalized_data = self._normalize_intent_data(
            user_question=cleaned_question,
            intent_data=intent_data,
        )

        return IntentResult.model_validate(
            normalized_data
        )

    @classmethod
    def _normalize_intent_data(
        cls,
        user_question: str,
        intent_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Repair conservative and unambiguous omissions from
        local-model output.

        The method only uses approved project metrics and
        dimensions. It does not invent business data.
        """

        normalized = dict(intent_data)
        question = user_question.strip().lower()

        normalized.setdefault(
            "business_objective",
            user_question.strip(),
        )

        normalized.setdefault(
            "metrics",
            [],
        )

        normalized.setdefault(
            "dimensions",
            [],
        )

        normalized.setdefault(
            "filters",
            [],
        )

        normalized.setdefault(
            "analysis_types",
            [],
        )

        normalized.setdefault(
            "ambiguity_reasons",
            [],
        )

        normalized.setdefault(
            "clarification_required",
            False,
        )

        normalized.setdefault(
            "clarification_question",
            None,
        )

        normalized.setdefault(
            "unsupported_request",
            False,
        )

        normalized.setdefault(
            "unsupported_reason",
            None,
        )

        normalized.setdefault(
            "confidence",
            0.7,
        )

        normalized["metrics"] = cls._normalize_list(
            normalized.get("metrics")
        )

        normalized["dimensions"] = (
            cls._normalize_list(
                normalized.get("dimensions")
            )
        )

        normalized["analysis_types"] = (
            cls._normalize_list(
                normalized.get(
                    "analysis_types"
                )
            )
        )

        normalized["ambiguity_reasons"] = (
            cls._normalize_list(
                normalized.get(
                    "ambiguity_reasons"
                )
            )
        )

        # First handle requests clearly outside the
        # connected Northwind business dataset.
        if cls._is_clearly_unsupported(
            question
        ):
            normalized[
                "unsupported_request"
            ] = True

            normalized[
                "unsupported_reason"
            ] = (
                "The connected Northwind dataset "
                "contains customers, orders, products, "
                "categories, suppliers, employees and "
                "shipping data, but it does not contain "
                "the requested external-domain data."
            )

            normalized[
                "clarification_required"
            ] = False

            normalized[
                "clarification_question"
            ] = None

            # Remove irrelevant analytical fields that the
            # local model may have generated.
            normalized["metrics"] = []
            normalized["dimensions"] = []
            normalized["filters"] = []
            normalized["analysis_types"] = []
            normalized["sort_direction"] = None
            normalized["limit"] = None
            normalized["time_range"] = None
            normalized["ambiguity_reasons"] = []

            return normalized
        # Ambiguous wording in the original question takes
        # precedence over a metric guessed by the LLM.
        #
        # Example:
        # "Why did performance fall?"
        #
        # The model may guess net_revenue, but the user did
        # not specify revenue. The workflow must therefore
        # request clarification instead of analyzing an
        # invented interpretation.
        if cls._contains_ambiguous_metric(
            question
        ):
            normalized["metrics"] = []

            normalized[
                "clarification_required"
            ] = True

            normalized[
                "clarification_question"
            ] = (
                "Which metric should I analyze: "
                "net revenue, gross revenue, order "
                "count, product quantity, or average "
                "order value?"
            )

            normalized[
                "unsupported_request"
            ] = False

            normalized[
                "unsupported_reason"
            ] = None

            ambiguity = (
                "The term 'performance' does not "
                "identify a specific measurable metric."
            )

            if (
                ambiguity
                not in normalized[
                    "ambiguity_reasons"
                ]
            ):
                normalized[
                    "ambiguity_reasons"
                ].append(
                    ambiguity
                )

            normalized[
                "analysis_types"
            ] = cls._merge_unique(
                normalized[
                    "analysis_types"
                ],
                [
                    AnalysisType.ROOT_CAUSE.value,
                    AnalysisType.COMPARISON.value,
                ],
            )

            normalized[
                "sort_direction"
            ] = None

            normalized["limit"] = None

            return normalized

        # Resolve explicit approved metrics if the local
        # model omitted them.
        if not normalized["metrics"]:
            inferred_metrics = (
                cls._infer_metrics(
                    question
                )
            )

            normalized["metrics"] = (
                inferred_metrics
            )

        # Normalize common aliases that a local model may
        # return instead of canonical metric names.
        normalized["metrics"] = (
            cls._canonicalize_metrics(
                normalized["metrics"]
            )
        )

        # Infer dimensions only when wording is explicit.
        inferred_dimensions = (
            cls._infer_dimensions(
                question
            )
        )

        normalized["dimensions"] = (
            cls._merge_unique(
                normalized["dimensions"],
                inferred_dimensions,
            )
        )

        # Add supported filters when explicit values are
        # present and the model omitted them.
        normalized["filters"] = (
    cls._normalize_filters(
        question=user_question.strip(),
        existing_filters=(
            normalized.get(
                "filters",
                []
            )
        ),
    )
)

        # Infer safe analytical operations.
        normalized["analysis_types"] = (
            cls._merge_unique(
                normalized["analysis_types"],
                cls._infer_analysis_types(
                    question
                ),
            )
        )

        # Infer top-N semantics.
        ranking_limit = cls._extract_limit(
            question
        )

        if (
            normalized.get("limit") is None
            and ranking_limit is not None
        ):
            normalized["limit"] = (
                ranking_limit
            )

        if cls._is_descending_ranking(
            question
        ):
            normalized[
                "sort_direction"
            ] = SortDirection.DESCENDING.value

        elif cls._is_ascending_ranking(
            question
        ):
            normalized[
                "sort_direction"
            ] = SortDirection.ASCENDING.value

        # If normalization still cannot identify a metric,
        # stop for clarification rather than allowing the
        # Planning Agent to fail.
        if (
            not normalized["metrics"]
            and not normalized[
                "unsupported_request"
            ]
        ):
            normalized[
                "clarification_required"
            ] = True

            normalized[
                "clarification_question"
            ] = (
                "Which approved metric would you like "
                "to analyze: net revenue, gross revenue, "
                "order count, product quantity, or "
                "average order value?"
            )

            ambiguity = (
                "No approved metric could be identified "
                "from the question."
            )

            if (
                ambiguity
                not in normalized[
                    "ambiguity_reasons"
                ]
            ):
                normalized[
                    "ambiguity_reasons"
                ].append(
                    ambiguity
                )

        return normalized

    @staticmethod
    def _normalize_list(
        value: Any,
    ) -> list[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        return [value]

    @staticmethod
    def _merge_unique(
        existing: list[Any],
        additions: list[Any],
    ) -> list[Any]:
        merged: list[Any] = []

        for value in [
            *existing,
            *additions,
        ]:
            if value not in merged:
                merged.append(value)

        return merged

    @staticmethod
    def _is_clearly_unsupported(
        question: str,
    ) -> bool:
        unsupported_patterns = [
            r"\bstock market\b",
            r"\bshare price\b",
            r"\bcrypto(?:currency)?\b",
            r"\bbitcoin\b",
            r"\bweather\b",
            r"\bmedical\b",
            r"\bpatient\b",
            r"\btraffic forecast\b",
            r"\bsports score\b",
        ]

        return any(
            re.search(pattern, question)
            for pattern
            in unsupported_patterns
        )

    @staticmethod
    def _contains_ambiguous_metric(
        question: str,
    ) -> bool:
        ambiguous_terms = [
            r"\bperformance\b",
            r"\bresults\b",
            r"\bsuccess\b",
            r"\bdoing\b",
            r"\bhealth\b",
        ]

        explicit_metric_terms = [
            r"\brevenue\b",
            r"\bsales\b",
            r"\bincome\b",
            r"\border count\b",
            r"\borders\b",
            r"\bquantity\b",
            r"\bunits\b",
            r"\baverage order value\b",
            r"\baov\b",
            r"\bgross revenue\b",
        ]

        has_ambiguous_term = any(
            re.search(pattern, question)
            for pattern
            in ambiguous_terms
        )

        has_explicit_metric = any(
            re.search(pattern, question)
            for pattern
            in explicit_metric_terms
        )

        return (
            has_ambiguous_term
            and not has_explicit_metric
        )

    @staticmethod
    def _canonicalize_metrics(
        metrics: list[Any],
    ) -> list[str]:
        aliases = {
            "sales": "net_revenue",
            "revenue": "net_revenue",
            "income": "net_revenue",
            "net revenue": "net_revenue",
            "net_revenue": "net_revenue",
            "gross revenue": "gross_revenue",
            "gross_revenue": "gross_revenue",
            "orders": "order_count",
            "order count": "order_count",
            "order_count": "order_count",
            "quantity": "product_quantity",
            "units": "product_quantity",
            "product quantity": "product_quantity",
            "product_quantity": "product_quantity",
            "average order value": "average_order_value",
            "aov": "average_order_value",
            "average_order_value": "average_order_value",
        }

        canonical: list[str] = []

        for metric in metrics:
            metric_text = str(metric).strip()
            metric_key = metric_text.lower()

            resolved = resolve_business_term(
                metric_key
            )

            if (
                resolved
                and "metric" in resolved
            ):
                canonical_metric = str(
                    resolved["metric"]
                )
            else:
                canonical_metric = aliases.get(
                    metric_key,
                    metric_text,
                )

            if canonical_metric not in canonical:
                canonical.append(
                    canonical_metric
                )

        return canonical

    @staticmethod
    def _infer_metrics(
        question: str,
    ) -> list[str]:
        metrics: list[str] = []

        # Check more specific phrases first.
        if re.search(
            r"\baverage order value\b|\baov\b",
            question,
        ):
            metrics.append(
                "average_order_value"
            )

        if re.search(
            r"\bgross revenue\b|\bgross sales\b",
            question,
        ):
            metrics.append(
                "gross_revenue"
            )

        elif re.search(
            r"\bnet revenue\b|\brevenue\b|\bsales\b|\bincome\b",
            question,
        ):
            metrics.append(
                "net_revenue"
            )

        if re.search(
            r"\bhow many orders\b|\bnumber of orders\b|\border count\b|\bcount of orders\b",
            question,
        ):
            metrics.append(
                "order_count"
            )

        if re.search(
            r"\bquantity\b|\bunits sold\b|\bproduct quantity\b",
            question,
        ):
            metrics.append(
                "product_quantity"
            )

        return IntentUnderstandingAgent._merge_unique(
            [],
            metrics,
        )

    @staticmethod
    def _infer_dimensions(
        question: str,
    ) -> list[str]:
        mappings = [
            (
                r"\bcategory\b|\bcategories\b",
                "category",
            ),
            (
                r"\bproduct\b|\bproducts\b",
                "product",
            ),
            (
                r"\bcustomer\b|\bcustomers\b",
                "customer",
            ),
            (
                r"\bsupplier\b|\bsuppliers\b",
                "supplier",
            ),
            (
                r"\bemployee\b|\bemployees\b",
                "employee",
            ),
            (
                r"\bmonthly\b|\bby month\b",
                "order_month",
            ),
            (
                r"\bquarterly\b|\bby quarter\b",
                "order_quarter",
            ),
            (
                r"\byearly\b|\bby year\b|\bannual\b",
                "order_year",
            ),
        ]

        dimensions: list[str] = []

        for pattern, dimension in mappings:
            if re.search(
                pattern,
                question,
            ):
                dimensions.append(
                    dimension
                )

        return dimensions

    @staticmethod
    def _normalize_filters(
        question: str,
        existing_filters: Any,
    ) -> list:
        """
        Preserve existing filters and extract explicit
        shipping-country or customer-country filters.

        General geographic wording defaults to shipping
        geography unless the question explicitly refers
        to customers.
        """

        filters = (
            list(existing_filters)
            if isinstance(
                existing_filters,
                list,
            )
            else []
        )

        existing_filter_fields = {
            (
                item.get("field")
                if isinstance(item, dict)
                else getattr(
                    item,
                    "field",
                    None,
                )
            )
            for item in filters
        }

        def clean_filter_value(
            value: str,
        ) -> str:
            return (
                value.strip()
                .strip(
                    ".,;:!?\"'"
                )
            )

        # Explicit shipping geography:
        # "orders shipped to Germany"
        # "shipped to country France"
        shipping_match = re.search(
            (
                r"\b(?:orders?\s+)?"
                r"(?:shipped|delivered)\s+to"
                r"(?:\s+country)?\s+"
                r"([A-Za-z][A-Za-z0-9_ -]*?)"
                r"(?="
                r"\s+(?:by|for|during|between|in)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            question,
            flags=re.IGNORECASE,
        )

        # Explicit customer geography:
        # "customers in Germany"
        # "customers based in France"
        customer_country_match = re.search(
            (
                r"\bcustomers?\s+"
                r"(?:based\s+in|located\s+in|"
                r"from|in)\s+"
                r"([A-Za-z][A-Za-z0-9_ -]*?)"
                r"(?="
                r"\s+(?:by|for|during|between)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            question,
            flags=re.IGNORECASE,
        )

        # General analytical geography:
        # "revenue in Germany"
        # "sales in France"
        # "orders in Brazil"
        #
        # This fallback is used only when neither shipping
        # nor customer geography was explicitly stated.
        general_country_match = re.search(
            (
                r"\b(?:revenue|sales|orders?|"
                r"net\s+revenue|gross\s+revenue)"
                r"(?:\s+\w+){0,4}?\s+in\s+"
                r"([A-Za-z][A-Za-z0-9_ -]*?)"
                r"(?="
                r"\s+(?:by|for|during|between|"
                r"ranked|rank|grouped)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            question,
            flags=re.IGNORECASE,
        )

        if (
            shipping_match
            and "ship_country"
            not in existing_filter_fields
        ):
            country = clean_filter_value(
                shipping_match.group(1)
            )

            if country:
                filters.append(
                    IntentFilter(
                        field="ship_country",
                        operator="equals",
                        value=country,
                    ).model_dump(
                        mode="json"
                    )
                )

                existing_filter_fields.add(
                    "ship_country"
                )

        if (
            customer_country_match
            and "customer_country"
            not in existing_filter_fields
        ):
            country = clean_filter_value(
                customer_country_match.group(1)
            )

            if country:
                filters.append(
                    IntentFilter(
                        field="customer_country",
                        operator="equals",
                        value=country,
                    ).model_dump(
                        mode="json"
                    )
                )

                existing_filter_fields.add(
                    "customer_country"
                )

        if (
            not shipping_match
            and not customer_country_match
            and general_country_match
            and "ship_country"
            not in existing_filter_fields
            and "customer_country"
            not in existing_filter_fields
        ):
            country = clean_filter_value(
                general_country_match.group(1)
            )

            if country:
                filters.append(
                    IntentFilter(
                        field="ship_country",
                        operator="equals",
                        value=country,
                    ).model_dump(
                        mode="json"
                    )
                )

        return filters
    @staticmethod
    def _infer_analysis_types(
        question: str,
    ) -> list[str]:
        analysis_types: list[str] = []

        if re.search(
            r"\btop\b|\bhighest\b|\bmost\b|\bbottom\b|\blowest\b|\bleast\b|\brank\b",
            question,
        ):
            analysis_types.append(
                AnalysisType.RANKING.value
            )

        if re.search(
            r"\bcompare\b|\bversus\b|\bvs\.?\b|\bdifference\b",
            question,
        ):
            analysis_types.append(
                AnalysisType.COMPARISON.value
            )

        if re.search(
            r"\bmonthly\b|\bquarterly\b|\byearly\b|\btrend\b|\bover time\b",
            question,
        ):
            analysis_types.append(
                AnalysisType.TREND.value
            )

        if re.search(
            r"\bwhy\b|\bcause\b|\bdriver\b",
            question,
        ):
            analysis_types.append(
                AnalysisType.ROOT_CAUSE.value
            )

        if re.search(
            r"\bhow many\b|\btotal\b|\bsum\b|\baverage\b",
            question,
        ):
            analysis_types.append(
                AnalysisType.AGGREGATION.value
            )

        # Ranking and grouped metric questions inherently
        # require aggregation.
        if (
            AnalysisType.RANKING.value
            in analysis_types
        ):
            analysis_types.append(
                AnalysisType.AGGREGATION.value
            )

        return (
            IntentUnderstandingAgent._merge_unique(
                [],
                analysis_types,
            )
        )

    @staticmethod
    def _extract_limit(
        question: str,
    ) -> int | None:
        numeric_match = re.search(
            r"\b(?:top|bottom)\s+(\d{1,3})\b",
            question,
        )

        if numeric_match:
            return min(
                int(
                    numeric_match.group(1)
                ),
                100,
            )

        word_numbers = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

        word_match = re.search(
            (
                r"\b(?:top|bottom)\s+"
                r"(one|two|three|four|five|six|"
                r"seven|eight|nine|ten)\b"
            ),
            question,
        )

        if word_match:
            return word_numbers[
                word_match.group(1)
            ]

        return None

    @staticmethod
    def _is_descending_ranking(
        question: str,
    ) -> bool:
        return bool(
            re.search(
                r"\btop\b|\bhighest\b|\bmost\b|\bbest\b",
                question,
            )
        )

    @staticmethod
    def _is_ascending_ranking(
        question: str,
    ) -> bool:
        return bool(
            re.search(
                r"\bbottom\b|\blowest\b|\bleast\b|\bworst\b",
                question,
            )
        )