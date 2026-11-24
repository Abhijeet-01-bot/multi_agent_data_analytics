from __future__ import annotations

from schemas.intent_schemas import (
    AnalysisType,
    IntentResult,
)
from schemas.query_spec_schemas import (
    QueryFilter,
    QueryOperation,
    QuerySortDirection,
    QuerySpec,
)
from semantic.query_registry import (
    DIMENSIONS,
    FILTER_FIELDS,
    METRICS,
)


def build_query_spec(
    intent: IntentResult,
) -> QuerySpec:
    if intent.clarification_required:
        raise ValueError(
            "The request requires clarification."
        )

    if intent.unsupported_request:
        raise ValueError(
            "The request requires unavailable data."
        )

    if len(intent.metrics) != 1:
        raise ValueError(
            "The query compiler currently requires "
            "exactly one metric."
        )

    metric = intent.metrics[0]

    if metric not in METRICS:
        raise ValueError(
            f"Unsupported metric: {metric}"
        )

    unknown_dimensions = [
        dimension
        for dimension in intent.dimensions
        if dimension not in DIMENSIONS
    ]

    if unknown_dimensions:
        raise ValueError(
            "Unsupported dimension(s): "
            + ", ".join(unknown_dimensions)
        )

    query_filters: list[QueryFilter] = []

    for intent_filter in intent.filters:
        if (
            intent_filter.field
            not in FILTER_FIELDS
        ):
            raise ValueError(
                "Unsupported filter field: "
                f"{intent_filter.field}"
            )

        filter_value = (
            intent_filter.value
        )

        # Ignore a missing value.
        if filter_value is None:
            continue

        # Ignore an empty string value.
        if (
            isinstance(
                filter_value,
                str,
            )
            and not filter_value.strip()
        ):
            continue

        # Ignore an empty collection, while allowing
        # non-empty IN and BETWEEN values.
        if (
            isinstance(
                filter_value,
                (list, tuple, set),
            )
            and len(filter_value) == 0
        ):
            continue

        query_filters.append(
            QueryFilter(
                field=intent_filter.field,
                operator=(
                    intent_filter.operator
                ),
                value=filter_value,
            )
        )

    analysis_values = {
        item.value
        for item in intent.analysis_types
    }

    operations = [
        QueryOperation.AGGREGATE
    ]

    if AnalysisType.RANKING.value in analysis_values:
        operations.append(
            QueryOperation.RANK
        )

    if (
        AnalysisType.COMPARISON.value
        in analysis_values
    ):
        operations.append(
            QueryOperation.COMPARE
        )

    if AnalysisType.TREND.value in analysis_values:
        operations.append(
            QueryOperation.TREND
        )

    sort_direction = None

    if intent.sort_direction is not None:
        sort_direction = QuerySortDirection(
            intent.sort_direction.value
        )

    if (
        QueryOperation.RANK in operations
        and sort_direction is None
    ):
        sort_direction = (
            QuerySortDirection.DESCENDING
        )

    return QuerySpec(
        metric=metric,
        dimensions=list(intent.dimensions),
        filters=query_filters,
        operations=operations,
        sort_direction=sort_direction,
        limit=intent.limit,
    )