from __future__ import annotations

from schemas.capability_schemas import (
    CapabilityAssessment,
    SupportStatus,
)
from schemas.intent_schemas import (
    IntentResult,
)


SUPPORTED_METRICS = {
    "net_revenue",
    "gross_revenue",
    "order_count",
    "product_quantity",
    "average_order_value",
}


SUPPORTED_DIMENSIONS = {
    "category",
    "product",
    "customer",
    "customer_country",
    "ship_country",
    "supplier",
    "employee",
    "order_date",
    "order_month",
    "order_quarter",
    "order_year",
}


SUPPORTED_OPERATIONS = {
    "aggregation",
    "filtering",
    "ranking",
    "comparison",
    "trend",
}


PARTIALLY_SUPPORTED_OPERATIONS = {
    "contribution",
    "root_cause",
    "anomaly_detection",
}


def assess_capability(
    intent: IntentResult,
) -> CapabilityAssessment:
    """
    Determine whether the current application can safely
    execute the interpreted request.
    """

    if intent.clarification_required:
        return CapabilityAssessment(
            support_status=(
                SupportStatus
                .NEEDS_CLARIFICATION
            ),
            reason=(
                intent.clarification_question
                or (
                    "The question does not identify "
                    "a sufficiently clear metric, "
                    "dimension, filter, or period."
                )
            ),
            required_metrics=(
                intent.metrics
            ),
            required_dimensions=(
                intent.dimensions
            ),
            required_operations=[
                operation.value
                for operation
                in intent.analysis_types
            ],
            suggested_questions=[
                (
                    "Show total net revenue."
                ),
                (
                    "Show order count by year."
                ),
                (
                    "Show the top five categories "
                    "by net revenue."
                ),
            ],
        )

    if intent.unsupported_request:
        return CapabilityAssessment(
            support_status=(
                SupportStatus.UNSUPPORTED_DATA
            ),
            reason=(
                intent.unsupported_reason
                or (
                    "The connected Northwind database "
                    "does not contain the required data."
                )
            ),
            suggested_questions=[
                (
                    "Show the top five categories "
                    "by net revenue."
                ),
                (
                    "Show monthly order count."
                ),
            ],
        )

    requested_metrics = set(
        intent.metrics
    )

    requested_dimensions = set(
        intent.dimensions
    )

    requested_operations = {
        operation.value
        for operation
        in intent.analysis_types
    }

    missing_metrics = sorted(
        requested_metrics
        - SUPPORTED_METRICS
    )

    missing_dimensions = sorted(
        requested_dimensions
        - SUPPORTED_DIMENSIONS
    )

    if missing_metrics or missing_dimensions:
        return CapabilityAssessment(
            support_status=(
                SupportStatus.UNSUPPORTED_DATA
            ),
            reason=(
                "The request requires metrics or "
                "dimensions that are not defined in "
                "the current Northwind semantic layer."
            ),
            required_metrics=sorted(
                requested_metrics
            ),
            required_dimensions=sorted(
                requested_dimensions
            ),
            required_operations=sorted(
                requested_operations
            ),
            missing_metrics=missing_metrics,
            missing_dimensions=(
                missing_dimensions
            ),
            suggested_questions=[
                (
                    "Show net revenue by category."
                ),
                (
                    "Show order count by customer "
                    "country."
                ),
            ],
        )

    unsupported_operations = sorted(
        requested_operations
        - SUPPORTED_OPERATIONS
    )

    if unsupported_operations:
        readable_operations = ", ".join(
            unsupported_operations
        )

        return CapabilityAssessment(
            support_status=(
                SupportStatus
                .UNSUPPORTED_ANALYSIS
            ),
            reason=(
                "The required data is available, "
                "but these analytical operations are "
                "not yet implemented safely: "
                f"{readable_operations}."
            ),
            required_metrics=sorted(
                requested_metrics
            ),
            required_dimensions=sorted(
                requested_dimensions
            ),
            required_operations=sorted(
                requested_operations
            ),
            unsupported_operations=(
                unsupported_operations
            ),
            suggested_questions=[
                (
                    "Show annual net revenue by "
                    "category."
                ),
                (
                    "Rank categories by total net "
                    "revenue."
                ),
                (
                    "Compare net revenue across "
                    "categories."
                ),
            ],
        )

    if not requested_metrics:
        return CapabilityAssessment(
            support_status=(
                SupportStatus
                .NEEDS_CLARIFICATION
            ),
            reason=(
                "No approved business metric could "
                "be identified from the question."
            ),
            suggested_questions=[
                (
                    "Show total net revenue."
                ),
                (
                    "How many orders are there?"
                ),
            ],
        )

    return CapabilityAssessment(
        support_status=(
            SupportStatus.SUPPORTED
        ),
        reason=(
            "The required metric, dimensions, and "
            "analytical operations are available."
        ),
        required_metrics=sorted(
            requested_metrics
        ),
        required_dimensions=sorted(
            requested_dimensions
        ),
        required_operations=sorted(
            requested_operations
        ),
    )