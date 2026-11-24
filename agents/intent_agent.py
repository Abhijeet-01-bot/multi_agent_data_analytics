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

        normalized_data = (
            self._normalize_intent_data(
                user_question=(
                    cleaned_question
                ),
                intent_data=intent_data,
            )
        )

        # Final defensive normalization before Pydantic
        # validates the IntentResult.
        normalized_data["filters"] = (
            self._flatten_filters(
                normalized_data.get(
                    "filters",
                    [],
                )
            )
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
        known_category_phrases = {
            "beverages",
            "condiments",
            "confections",
            "dairy products",
            "grains/cereals",
            "meat/poultry",
            "produce",
            "seafood",
        }

        lower_question = (
            user_question.lower()
        )

        category_names_present = any(
            category_phrase
            in lower_question
            for category_phrase
            in known_category_phrases
        )

        explicit_product_request = bool(
            re.search(
                (
                    r"\bproduct-level\b"
                    r"|\bby product\b"
                    r"|\bindividual products\b"
                    r"|\bproduct names?\b"
                ),
                lower_question,
            )
        )

        if (
            category_names_present
            and not explicit_product_request
        ):
            normalized[
                "dimensions"
            ] = [
                dimension
                for dimension
                in normalized[
                    "dimensions"
                ]
                if dimension != "product"
            ]

        normalized["analysis_types"] = (
            cls._normalize_list(
                normalized.get(
                    "analysis_types"
                )
            )
        )        
        analysis_type_values = set(
            normalized[
                "analysis_types"
            ]
        )

        if (
            AnalysisType.RANKING.value
            not in analysis_type_values
        ):
            normalized[
                "sort_direction"
            ] = None

            normalized["limit"] = None

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
        # Clean dimensions only after model-provided and
        # deterministically inferred dimensions have been
        # merged.
        normalized["dimensions"] = (
            cls._normalize_dimensions(
                user_question=(
                    user_question
                ),
                dimensions=(
                    normalized[
                        "dimensions"
                    ]
                ),
            )
        )

        # Normalize general filters such as shipping
        # country and customer country.
        normalized["filters"] = (
            cls._normalize_filters(
                question=user_question.strip(),
                existing_filters=(
                    normalized.get(
                        "filters",
                        [],
                    )
                ),
            )
        )

        # Add category values such as Beverages and
        # Dairy Products when explicitly mentioned.
        normalized["filters"] = (
            cls._normalize_category_filters(
                question=user_question.strip(),
                dimensions=(
                    normalized[
                        "dimensions"
                    ]
                ),
                existing_filters=(
                    normalized[
                        "filters"
                    ]
                ),
            )
        )

        # Flatten any nested filter lists returned by the
        # local model or introduced by normalization.
        normalized["filters"] = (
            cls._flatten_filters(
                normalized.get(
                    "filters",
                    [],
                )
            )
        )

        # Remove filters with missing or empty values.
        cleaned_filters: list = []

        for intent_filter in normalized[
            "filters"
        ]:
            if isinstance(
                intent_filter,
                dict,
            ):
                filter_value = (
                    intent_filter.get(
                        "value"
                    )
                )
            else:
                filter_value = getattr(
                    intent_filter,
                    "value",
                    None,
                )

            if filter_value is None:
                continue

            if (
                isinstance(
                    filter_value,
                    str,
                )
                and not filter_value.strip()
            ):
                continue

            if (
                isinstance(
                    filter_value,
                    (list, tuple, set),
                )
                and len(filter_value) == 0
            ):
                continue

            cleaned_filters.append(
                intent_filter
            )

        normalized["filters"] = (
            cleaned_filters
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
    def _normalize_dimensions(
        user_question: str,
        dimensions: list[str],
    ) -> list[str]:
        """
        Remove dimensions inferred from words that are
        actually part of known Northwind entity values.

        Example:
        "Dairy Products" is a category value. It must not
        cause the product dimension to be added.
        """

        normalized_dimensions = list(
            dict.fromkeys(dimensions)
        )

        lower_question = (
            user_question.strip().lower()
        )

        known_category_names = {
            "beverages",
            "condiments",
            "confections",
            "dairy products",
            "grains/cereals",
            "meat/poultry",
            "produce",
            "seafood",
        }

        contains_category_name = any(
            category_name in lower_question
            for category_name
            in known_category_names
        )

        explicit_product_dimension = bool(
            re.search(
                (
                    r"\bby\s+product\b"
                    r"|\bproduct[- ]level\b"
                    r"|\bindividual\s+products?\b"
                    r"|\bproduct\s+names?\b"
                    r"|\bproducts?\s+by\b"
                ),
                lower_question,
                flags=re.IGNORECASE,
            )
        )

        if (
            contains_category_name
            and not explicit_product_dimension
        ):
            normalized_dimensions = [
                dimension
                for dimension
                in normalized_dimensions
                if dimension != "product"
            ]

        return normalized_dimensions
     
    @staticmethod
    def _infer_dimensions(
        question: str,
    ) -> list[str]:
        mappings = [
                        (
                (
                    r"\bcategory\b"
                    r"|\bcategories\b"
                    r"|\bbeverages\b"
                    r"|\bcondiments\b"
                    r"|\bconfections\b"
                    r"|\bdairy products\b"
                    r"|\bgrains/cereals\b"
                    r"|\bmeat/poultry\b"
                    r"|\bproduce\b"
                    r"|\bseafood\b"
                ),
                "category",
            ),
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
    def _flatten_filters(
        filters: object,
    ) -> list:
        """
        Flatten nested filter collections.

        Examples:
        [[{"field": "ship_country", ...}]]
        becomes:
        [{"field": "ship_country", ...}]

        [[]] becomes [].
        """

        if filters is None:
            return []

        if not isinstance(
            filters,
            (list, tuple),
        ):
            return [filters]

        flattened: list = []

        for item in filters:
            if isinstance(
                item,
                (list, tuple),
            ):
                flattened.extend(
                    IntentUnderstandingAgent
                    ._flatten_filters(
                        item
                    )
                )
            else:
                flattened.append(
                    item
                )

        return flattened
    
    @staticmethod
    def _normalize_filters(
        question: str,
        existing_filters: object,
    ) -> list:
        """
        Preserve existing filters and extract explicit
        geographic filters from the original question.
        """

        filters = (
            IntentUnderstandingAgent
            ._flatten_filters(
                existing_filters
            )
        )

        existing_fields = {
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

        def clean_value(
            value: str,
        ) -> str:
            return value.strip().strip(
                ".,;:!?\"'"
            )

        shipping_pattern = re.compile(
            (
                r"\b(?:orders?\s+)?"
                r"(?:shipped|delivered)\s+to"
                r"(?:\s+country)?\s+"
                r"([A-Za-z][A-Za-z0-9_ /-]*?)"
                r"(?="
                r"\s+(?:by|for|during|between)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            flags=re.IGNORECASE,
        )

        customer_pattern = re.compile(
            (
                r"\bcustomers?\s+"
                r"(?:based\s+in|located\s+in|from|in)"
                r"\s+"
                r"([A-Za-z][A-Za-z0-9_ /-]*?)"
                r"(?="
                r"\s+(?:by|for|during|between)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            flags=re.IGNORECASE,
        )

        general_country_pattern = re.compile(
            (
                r"\b(?:net\s+revenue|gross\s+revenue|"
                r"revenue|sales|orders?)"
                r"(?:\s+\w+){0,4}?\s+in\s+"
                r"([A-Za-z][A-Za-z0-9_ /-]*?)"
                r"(?="
                r"\s+(?:by|for|during|between|"
                r"ranked|rank|grouped)\b"
                r"|[.,;:!?]"
                r"|$"
                r")"
            ),
            flags=re.IGNORECASE,
        )

        shipping_match = shipping_pattern.search(
            question
        )

        customer_match = customer_pattern.search(
            question
        )

        general_match = (
            general_country_pattern.search(
                question
            )
        )

        if (
            shipping_match is not None
            and "ship_country"
            not in existing_fields
        ):
            country = clean_value(
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

                existing_fields.add(
                    "ship_country"
                )

        if (
            customer_match is not None
            and "customer_country"
            not in existing_fields
        ):
            country = clean_value(
                customer_match.group(1)
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

                existing_fields.add(
                    "customer_country"
                )

        if (
            shipping_match is None
            and customer_match is None
            and general_match is not None
            and "ship_country"
            not in existing_fields
            and "customer_country"
            not in existing_fields
        ):
            country = clean_value(
                general_match.group(1)
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
    def _normalize_category_filters(
        question: str,
        dimensions: list[str],
        existing_filters: object,
    ) -> list:
        """
        Extract explicitly mentioned Northwind category
        values from the user question.
        """

        filters = (
            IntentUnderstandingAgent
            ._flatten_filters(
                existing_filters
            )
        )

        if "category" not in dimensions:
            return filters

        category_filter_exists = any(
            (
                item.get("field")
                if isinstance(item, dict)
                else getattr(
                    item,
                    "field",
                    None,
                )
            )
            == "category"
            for item in filters
        )

        if category_filter_exists:
            return filters

        known_categories = [
            "Beverages",
            "Condiments",
            "Confections",
            "Dairy Products",
            "Grains/Cereals",
            "Meat/Poultry",
            "Produce",
            "Seafood",
        ]

        lowercase_question = (
            question.lower()
        )

        matches = [
            category
            for category in known_categories
            if category.lower()
            in lowercase_question
        ]

        if len(matches) == 1:
            filters.append(
                IntentFilter(
                    field="category",
                    operator="equals",
                    value=matches[0],
                ).model_dump(
                    mode="json"
                )
            )

        elif len(matches) > 1:
            filters.append(
                IntentFilter(
                    field="category",
                    operator="in",
                    value=matches,
                ).model_dump(
                    mode="json"
                )
            )

        return filters

    @staticmethod
    def _infer_analysis_types(
        question: str,
    ) -> list:
        """
        Infer supported analytical operations from the
        original user question.

        This method adds only operation types supported by
        the current IntentResult schema.
        """

        analysis_types: list[str] = []

        if re.search(
            (
                r"\btop\b"
                r"|\bbottom\b"
                r"|\bhighest\b"
                r"|\blowest\b"
                r"|\bmost\b"
                r"|\bleast\b"
                r"|\brank\b"
                r"|\branking\b"
            ),
            question,
            flags=re.IGNORECASE,
        ):
            analysis_types.append(
                AnalysisType.RANKING.value
            )

        if re.search(
            (
                r"\bcompare\b"
                r"|\bcomparison\b"
                r"|\bversus\b"
                r"|\bvs\.?\b"
                r"|\bdifference\b"
                r"|\bbetween\b"
            ),
            question,
            flags=re.IGNORECASE,
        ):
            analysis_types.append(
                AnalysisType.COMPARISON.value
            )

        if re.search(
            (
                r"\bmonthly\b"
                r"|\bby month\b"
                r"|\bquarterly\b"
                r"|\bby quarter\b"
                r"|\byearly\b"
                r"|\bby year\b"
                r"|\bannual\b"
                r"|\bover time\b"
                r"|\btrend\b"
                r"|\bthroughout the years\b"
                r"|\byear[- ]over[- ]year\b"
            ),
            question,
            flags=re.IGNORECASE,
        ):
            analysis_types.append(
                AnalysisType.TREND.value
            )

        if re.search(
            (
                r"\bwhy\b"
                r"|\bcause\b"
                r"|\bcaused\b"
                r"|\bdriver\b"
                r"|\bdriven by\b"
            ),
            question,
            flags=re.IGNORECASE,
        ):
            analysis_types.append(
                AnalysisType.ROOT_CAUSE.value
            )

        if re.search(
            (
                r"\bhow many\b"
                r"|\btotal\b"
                r"|\bsum\b"
                r"|\baverage\b"
                r"|\brevenue\b"
                r"|\bsales\b"
                r"|\bcount\b"
                r"|\bquantity\b"
                r"|\bunits\b"
            ),
            question,
            flags=re.IGNORECASE,
        ):
            analysis_types.append(
                AnalysisType.AGGREGATION.value
            )

        # Ranking, comparison, and trend queries normally
        # aggregate a metric by one or more dimensions.
        if any(
            analysis_type
            in analysis_types
            for analysis_type in {
                AnalysisType.RANKING.value,
                AnalysisType.COMPARISON.value,
                AnalysisType.TREND.value,
            }
        ):
            analysis_types.append(
                AnalysisType.AGGREGATION.value
            )

        return (
            IntentUnderstandingAgent
            ._merge_unique(
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