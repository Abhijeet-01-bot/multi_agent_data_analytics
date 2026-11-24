from __future__ import annotations

from typing import Any, Protocol

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from config.llm import create_llm
from config.settings import settings
from prompts.reporting_prompt import (
    REPORTING_SYSTEM_PROMPT,
    build_reporting_user_prompt,
)
from schemas.analysis_schemas import (
    AnalysisResult,
)
from schemas.evidence_schemas import (
    EvidenceBundle,
)
from schemas.intent_schemas import (
    IntentResult,
)
from schemas.planning_schemas import (
    ExecutionPlan,
)
from schemas.report_schemas import (
    ExecutiveReport,
)


class StructuredReportingModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> Any:
        ...


class ReportingAgent:
    """
    Transform evidence-grounded findings into an
    executive business report.

    Local models return a dictionary first. Predictable
    field omissions are normalized before final Pydantic
    validation.
    """

    def __init__(
        self,
        structured_model: (
            StructuredReportingModel | None
        ) = None,
    ) -> None:
        self.uses_external_model = (
            structured_model is None
        )

        if structured_model is None:
            llm = create_llm()

            if (
                settings.llm_provider
                .strip()
                .lower()
                == "ollama"
            ):
                # Request a plain dictionary from Ollama.
                # This allows deterministic normalization
                # before final Pydantic validation.
                structured_model = (
                    llm.with_structured_output(
                        ExecutiveReport
                        .model_json_schema(),
                        method="json_schema",
                    )
                )

            else:
                structured_model = (
                    llm.with_structured_output(
                        ExecutiveReport,
                        method="json_schema",
                    )
                )

        self.structured_model = (
            structured_model
        )

    def create_report(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        analysis: AnalysisResult,
        evidence_bundle: EvidenceBundle,
    ) -> ExecutiveReport:
        """
        Generate, normalize, validate, and return an
        evidence-grounded executive report.
        """

        if not analysis.evidence_sufficient:
            raise ValueError(
                "The final report cannot be created "
                "because analysis evidence is "
                "insufficient."
            )

        if not analysis.findings:
            raise ValueError(
                "The final report requires at least "
                "one analytical finding."
            )

        if (
            evidence_bundle
            .validated_record_count
            == 0
        ):
            raise ValueError(
                "The final report requires validated "
                "evidence."
            )

        prompt = build_reporting_user_prompt(
            intent=intent,
            plan=plan,
            analysis=analysis,
            evidence_bundle=evidence_bundle,
        )

        messages = [
            SystemMessage(
                content=REPORTING_SYSTEM_PROMPT
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

        # Convert every provider result into a dictionary.
        # Every result then goes through the same
        # deterministic normalization path.
        if isinstance(
            raw_result,
            ExecutiveReport,
        ):
            report_data = (
                raw_result.model_dump(
                    mode="json"
                )
            )

        elif isinstance(
            raw_result,
            dict,
        ):
            report_data = dict(
                raw_result
            )

        elif hasattr(
            raw_result,
            "model_dump",
        ):
            report_data = (
                raw_result.model_dump(
                    mode="json"
                )
            )

        else:
            raise TypeError(
                "The Reporting Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        normalized_result = (
            self._normalize_report_data(
                report_data=report_data,
                evidence_bundle=(
                    evidence_bundle
                ),
            )
        )

        report = (
            ExecutiveReport.model_validate(
                normalized_result
            )
        )

        self._validate_references(
            report=report,
            analysis=analysis,
            evidence_bundle=evidence_bundle,
        )

        return report

    @staticmethod
    def _get_evidence_fields(
        evidence_id: str,
        evidence_bundle: EvidenceBundle,
    ) -> list[str]:
        """
        Return exact available fields from one validated
        evidence record.
        """

        evidence = next(
            (
                record
                for record
                in evidence_bundle.records
                if (
                    record.evidence_id
                    == evidence_id
                    and record.validated
                )
            ),
            None,
        )

        # Fixed: the old implementation incorrectly used
        # "if e", where e was undefined.
        if evidence is None:
            return []

        fields: list[str] = []

        # Query evidence normally exposes explicit source
        # columns.
        for field in (
            evidence.source_columns
            or []
        ):
            if field not in fields:
                fields.append(
                    field
                )

        # Read field names from query-result rows too.
        for row in (
            evidence.source_rows
            or []
        ):
            if not isinstance(
                row,
                dict,
            ):
                continue

            for field in row.keys():
                if field not in fields:
                    fields.append(
                        field
                    )

        # Calculation evidence normally stores rows under
        # calculation_output["records"].
        calculation_output = (
            evidence.calculation_output
            or {}
        )

        calculation_records = (
            calculation_output.get(
                "records",
                [],
            )
            if isinstance(
                calculation_output,
                dict,
            )
            else []
        )

        if isinstance(
            calculation_records,
            list,
        ):
            for row in calculation_records:
                if not isinstance(
                    row,
                    dict,
                ):
                    continue

                for field in row.keys():
                    if field not in fields:
                        fields.append(
                            field
                        )

        return fields

    @staticmethod
    def _humanize_field(
        field_name: str | None,
    ) -> str:
        """
        Convert canonical data fields into labels suitable
        for reports and charts.
        """

        if not field_name:
            return "Value"

        replacements = {
            "NetRevenue": "Net Revenue",
            "GrossRevenue": "Gross Revenue",
            "OrderCount": "Order Count",
            "ProductQuantity": (
                "Product Quantity"
            ),
            "AverageOrderValue": (
                "Average Order Value"
            ),
            "RevenueIncrease": (
                "Revenue Increase"
            ),
            "RevenueIncreasePercentage": (
                "Revenue Increase Percentage"
            ),
            "OrderMonth": "Month",
            "OrderQuarter": "Quarter",
            "OrderYear": "Year",
            "OrderDate": "Order Date",
            "CategoryName": "Category",
            "ProductName": "Product",
            "CustomerName": "Customer",
            "SupplierName": "Supplier",
            "EmployeeName": "Employee",
            "ShipCountry": "Shipping Country",
            "CustomerCountry": (
                "Customer Country"
            ),
            "period": "Period",
            "series": "Series",
            "label": "Label",
            "value": "Value",
        }

        return replacements.get(
            field_name,
            field_name,
        )

    @classmethod
    def _normalize_visualization(
        cls,
        visualization: dict[str, Any],
        evidence_bundle: EvidenceBundle,
    ) -> dict[str, Any]:
        """
        Complete predictable visualization fields using
        the exact columns available in validated evidence.

        The method maps evidence fields only. It never
        invents analytical values.
        """

        normalized = dict(
            visualization
        )

        chart_type = str(
            normalized.get(
                "chart_type",
                "",
            )
        ).strip().lower()

        evidence_id = str(
            normalized.get(
                "evidence_id",
                "",
            )
        ).strip()

        available_fields = (
            cls._get_evidence_fields(
                evidence_id=evidence_id,
                evidence_bundle=(
                    evidence_bundle
                ),
            )
        )

        field_set = set(
            available_fields
        )

        time_candidates = [
            "period",
            "OrderMonth",
            "OrderQuarter",
            "OrderYear",
            "OrderDate",
            "order_month",
            "order_quarter",
            "order_year",
            "order_date",
        ]

        # Prefer explicit business dimensions over generic
        # calculation fields such as "series" and "label".
        category_candidates = [
            "CategoryName",
            "ProductName",
            "CustomerName",
            "SupplierName",
            "EmployeeName",
            "ShipCountry",
            "CustomerCountry",
            "series",
            "label",
        ]

        # Prefer specific metric columns over the generic
        # deterministic-analysis field named "value".
        value_candidates = [
            "NetRevenue",
            "GrossRevenue",
            "OrderCount",
            "ProductQuantity",
            "AverageOrderValue",
            "RevenueIncrease",
            "RevenueIncreasePercentage",
            "value",
        ]

        time_field = next(
            (
                field
                for field
                in time_candidates
                if field in field_set
            ),
            None,
        )

        category_field = next(
            (
                field
                for field
                in category_candidates
                if field in field_set
            ),
            None,
        )

        value_field = next(
            (
                field
                for field
                in value_candidates
                if field in field_set
            ),
            None,
        )

        # If a new metric alias is introduced and it is
        # the only remaining field, use it as the metric.
        if value_field is None:
            excluded_fields = {
                item
                for item in [
                    time_field,
                    category_field,
                ]
                if item is not None
            }

            remaining_fields = [
                field
                for field
                in available_fields
                if field
                not in excluded_fields
            ]

            if len(remaining_fields) == 1:
                value_field = (
                    remaining_fields[0]
                )

        if chart_type == "line":
            if not normalized.get(
                "x_field"
            ):
                normalized["x_field"] = (
                    time_field
                )

            if not normalized.get(
                "y_field"
            ):
                normalized["y_field"] = (
                    value_field
                )

            if (
                not normalized.get(
                    "series_field"
                )
                and category_field
                and category_field
                not in {
                    normalized.get(
                        "x_field"
                    ),
                    normalized.get(
                        "y_field"
                    ),
                }
            ):
                normalized[
                    "series_field"
                ] = category_field

            if not normalized.get(
                "x_axis_title"
            ):
                normalized[
                    "x_axis_title"
                ] = (
                    cls._humanize_field(
                        time_field
                    )
                    if time_field
                    else "Period"
                )

            if not normalized.get(
                "y_axis_title"
            ):
                normalized[
                    "y_axis_title"
                ] = (
                    cls._humanize_field(
                        value_field
                    )
                    if value_field
                    else "Value"
                )

        elif chart_type in {
            "bar",
            "vertical_bar",
        }:
            if not normalized.get(
                "x_field"
            ):
                normalized["x_field"] = (
                    category_field
                )

            if not normalized.get(
                "y_field"
            ):
                normalized["y_field"] = (
                    value_field
                )

            if not normalized.get(
                "x_axis_title"
            ):
                normalized[
                    "x_axis_title"
                ] = (
                    cls._humanize_field(
                        category_field
                    )
                    if category_field
                    else "Category"
                )

            if not normalized.get(
                "y_axis_title"
            ):
                normalized[
                    "y_axis_title"
                ] = (
                    cls._humanize_field(
                        value_field
                    )
                    if value_field
                    else "Value"
                )

        elif (
            chart_type
            == "horizontal_bar"
        ):
            if not normalized.get(
                "x_field"
            ):
                normalized["x_field"] = (
                    value_field
                )

            if not normalized.get(
                "y_field"
            ):
                normalized["y_field"] = (
                    category_field
                )

            if not normalized.get(
                "x_axis_title"
            ):
                normalized[
                    "x_axis_title"
                ] = (
                    cls._humanize_field(
                        value_field
                    )
                    if value_field
                    else "Value"
                )

            if not normalized.get(
                "y_axis_title"
            ):
                normalized[
                    "y_axis_title"
                ] = (
                    cls._humanize_field(
                        category_field
                    )
                    if category_field
                    else "Category"
                )

        elif chart_type == "kpi":
            if not normalized.get(
                "value_field"
            ):
                normalized["value_field"] = (
                    value_field
                )

        elif chart_type == "table":
            # Tables do not require axis mappings.
            pass

        return normalized

    @staticmethod
    def _is_usable_visualization(
        visualization: dict[str, Any],
    ) -> bool:
        """
        Determine whether a normalized chart contains the
        fields required by its chart type.
        """

        chart_type = str(
            visualization.get(
                "chart_type",
                "",
            )
        ).strip().lower()

        if chart_type in {
            "line",
            "bar",
            "vertical_bar",
            "horizontal_bar",
        }:
            return bool(
                visualization.get(
                    "x_field"
                )
                and visualization.get(
                    "y_field"
                )
            )

        if chart_type == "kpi":
            return bool(
                visualization.get(
                    "value_field"
                )
            )

        if chart_type == "table":
            return True

        return False

    @classmethod
    def _build_fallback_visualization(
        cls,
        evidence_bundle: EvidenceBundle,
    ) -> dict[str, Any] | None:
        """
        Build a conservative visualization when the local
        model does not provide a usable chart.

        A fallback is returned only when the evidence
        provides an unambiguous field mapping.
        """

        for evidence in evidence_bundle.records:
            if not evidence.validated:
                continue

            fields = cls._get_evidence_fields(
                evidence_id=(
                    evidence.evidence_id
                ),
                evidence_bundle=(
                    evidence_bundle
                ),
            )

            field_set = set(
                fields
            )

            time_candidates = [
                "period",
                "OrderMonth",
                "OrderQuarter",
                "OrderYear",
                "OrderDate",
            ]

            value_candidates = [
                "NetRevenue",
                "GrossRevenue",
                "OrderCount",
                "ProductQuantity",
                "AverageOrderValue",
                "RevenueIncrease",
                "RevenueIncreasePercentage",
                "value",
            ]

            series_candidates = [
                "CategoryName",
                "ProductName",
                "CustomerName",
                "SupplierName",
                "EmployeeName",
                "ShipCountry",
                "CustomerCountry",
                "series",
            ]

            time_field = next(
                (
                    field
                    for field
                    in time_candidates
                    if field in field_set
                ),
                None,
            )

            value_field = next(
                (
                    field
                    for field
                    in value_candidates
                    if field in field_set
                ),
                None,
            )

            series_field = next(
                (
                    field
                    for field
                    in series_candidates
                    if field in field_set
                ),
                None,
            )

            # Trend evidence takes precedence over ranking
            # evidence because source rows and calculation
            # fields may coexist in one fixture.
            if (
                time_field
                and value_field
            ):
                return {
                    "visualization_id": (
                        "V-AUTO-1"
                    ),
                    "chart_type": "line",
                    "title": (
                        f"{cls._humanize_field(value_field)} "
                        "Trend"
                    ),
                    "description": (
                        "Validated metric values shown "
                        "over time."
                    ),
                    "evidence_id": (
                        evidence.evidence_id
                    ),
                    "x_field": time_field,
                    "y_field": value_field,
                    "series_field": (
                        series_field
                    ),
                    "x_axis_title": (
                        cls._humanize_field(
                            time_field
                        )
                    ),
                    "y_axis_title": (
                        cls._humanize_field(
                            value_field
                        )
                    ),
                    "show_values": False,
                    "metadata": {
                        "generated_by": (
                            "deterministic_fallback"
                        )
                    },
                }

            # Deterministic ranking evidence.
            if {
                "label",
                "value",
            }.issubset(field_set):
                calculation_output = (
                    evidence.calculation_output
                    or {}
                )

                metadata = (
                    calculation_output.get(
                        "metadata",
                        {},
                    )
                    if isinstance(
                        calculation_output,
                        dict,
                    )
                    else {}
                )

                label_column = (
                    metadata.get(
                        "label_column"
                    )
                    or "label"
                )

                value_column = (
                    metadata.get(
                        "value_column"
                    )
                    or "value"
                )

                return {
                    "visualization_id": (
                        "V-AUTO-1"
                    ),
                    "chart_type": (
                        "horizontal_bar"
                    ),
                    "title": (
                        f"{cls._humanize_field(label_column)} "
                        f"by "
                        f"{cls._humanize_field(value_column)}"
                    ),
                    "description": (
                        "Validated records ranked by "
                        "their calculated value."
                    ),
                    "evidence_id": (
                        evidence.evidence_id
                    ),
                    "x_field": "value",
                    "y_field": "label",
                    "value_field": "value",
                    "label_field": "label",
                    "sort_order": (
                        "descending"
                    ),
                    "top_n": None,
                    "x_axis_title": (
                        cls._humanize_field(
                            value_column
                        )
                    ),
                    "y_axis_title": (
                        cls._humanize_field(
                            label_column
                        )
                    ),
                    "show_values": True,
                    "metadata": {
                        "generated_by": (
                            "deterministic_fallback"
                        ),
                        "label_column": (
                            label_column
                        ),
                        "value_column": (
                            value_column
                        ),
                    },
                }

            # Single-row aggregate evidence becomes a KPI.
            numeric_candidates = [
                "NetRevenue",
                "GrossRevenue",
                "OrderCount",
                "ProductQuantity",
                "AverageOrderValue",
            ]

            numeric_field = next(
                (
                    field
                    for field
                    in numeric_candidates
                    if field in field_set
                ),
                None,
            )

            source_rows = (
                evidence.source_rows
                or []
            )

            if (
                numeric_field
                and len(source_rows) == 1
            ):
                return {
                    "visualization_id": (
                        "V-AUTO-1"
                    ),
                    "chart_type": "kpi",
                    "title": (
                        cls._humanize_field(
                            numeric_field
                        )
                    ),
                    "description": (
                        "Validated aggregate value."
                    ),
                    "evidence_id": (
                        evidence.evidence_id
                    ),
                    "value_field": (
                        numeric_field
                    ),
                    "show_values": True,
                    "metadata": {
                        "generated_by": (
                            "deterministic_fallback"
                        )
                    },
                }

        return None

    @classmethod
    def _normalize_report_data(
        cls,
        report_data: Any,
        evidence_bundle: EvidenceBundle,
    ) -> dict[str, Any]:
        """
        Normalize predictable local-model omissions before
        final Pydantic validation.

        Invalid optional visualizations are removed instead
        of causing the entire report to fail.
        """

        if hasattr(
            report_data,
            "model_dump",
        ):
            normalized_report = (
                report_data.model_dump(
                    mode="json"
                )
            )

        elif isinstance(
            report_data,
            dict,
        ):
            normalized_report = dict(
                report_data
            )

        else:
            raise TypeError(
                "The Reporting Agent returned an "
                "unsupported result type: "
                f"{type(report_data).__name__}"
            )

        normalized_report.setdefault(
            "findings",
            [],
        )

        normalized_report.setdefault(
            "recommendations",
            [],
        )

        normalized_report.setdefault(
            "limitations",
            [],
        )

        normalized_report.setdefault(
            "warnings",
            [],
        )

        raw_visualizations = (
            normalized_report.get(
                "visualizations",
                [],
            )
            or []
        )

        normalized_visualizations: list[
            dict[str, Any]
        ] = []

        visualization_warnings: list[str] = []

        for visualization in (
            raw_visualizations
        ):
            if hasattr(
                visualization,
                "model_dump",
            ):
                visualization_data = (
                    visualization.model_dump(
                        mode="json"
                    )
                )

            elif isinstance(
                visualization,
                dict,
            ):
                visualization_data = dict(
                    visualization
                )

            else:
                visualization_warnings.append(
                    "An unsupported visualization "
                    "entry was removed."
                )
                continue

            normalized_chart = (
                cls._normalize_visualization(
                    visualization=(
                        visualization_data
                    ),
                    evidence_bundle=(
                        evidence_bundle
                    ),
                )
            )

            if not cls._is_usable_visualization(
                normalized_chart
            ):
                visualization_id = (
                    normalized_chart.get(
                        "visualization_id",
                        "unknown",
                    )
                )

                visualization_warnings.append(
                    (
                        "Visualization "
                        f"{visualization_id} was removed "
                        "because its referenced evidence "
                        "did not provide the fields "
                        "required by its chart type."
                    )
                )
                continue

            normalized_visualizations.append(
                normalized_chart
            )

        # If the model did not provide a usable chart,
        # create one only when the evidence supports an
        # unambiguous mapping.
        if not normalized_visualizations:
            fallback_visualization = (
                cls._build_fallback_visualization(
                    evidence_bundle=(
                        evidence_bundle
                    )
                )
            )

            if fallback_visualization:
                normalized_visualizations.append(
                    fallback_visualization
                )

                visualization_warnings.append(
                    "A deterministic visualization "
                    "specification was generated because "
                    "the local model did not provide a "
                    "usable one."
                )

        normalized_report[
            "visualizations"
        ] = normalized_visualizations

        report_warnings = list(
            normalized_report.get(
                "warnings",
                [],
            )
            or []
        )

        for warning in visualization_warnings:
            if warning not in report_warnings:
                report_warnings.append(
                    warning
                )

        normalized_report[
            "warnings"
        ] = report_warnings

        # Derive used evidence IDs from every report
        # component. This prevents local-model omissions.
        referenced_evidence_ids: set[str] = set()

        for finding in normalized_report[
            "findings"
        ]:
            if not isinstance(
                finding,
                dict,
            ):
                continue

            referenced_evidence_ids.update(
                finding.get(
                    "evidence_ids",
                    [],
                )
                or []
            )

        for recommendation in normalized_report[
            "recommendations"
        ]:
            if not isinstance(
                recommendation,
                dict,
            ):
                continue

            referenced_evidence_ids.update(
                recommendation.get(
                    "evidence_ids",
                    [],
                )
                or []
            )

        for visualization in (
            normalized_visualizations
        ):
            evidence_id = visualization.get(
                "evidence_id"
            )

            if evidence_id:
                referenced_evidence_ids.add(
                    evidence_id
                )

        existing_evidence_ids = (
            normalized_report.get(
                "evidence_ids_used",
                [],
            )
            or []
        )

        referenced_evidence_ids.update(
            existing_evidence_ids
        )

        normalized_report[
            "evidence_ids_used"
        ] = sorted(
            referenced_evidence_ids
        )

        return normalized_report

    @staticmethod
    def _validate_references(
        report: ExecutiveReport,
        analysis: AnalysisResult,
        evidence_bundle: EvidenceBundle,
    ) -> None:
        """
        Ensure every finding and evidence reference in the
        report exists in validated upstream output.
        """

        valid_finding_ids = {
            finding.finding_id
            for finding in analysis.findings
        }

        valid_evidence_ids = {
            evidence.evidence_id
            for evidence
            in evidence_bundle.records
            if evidence.validated
        }

        unknown_finding_ids: set[str] = set()
        unknown_evidence_ids: set[str] = set()

        for finding in report.findings:
            if (
                finding.finding_id
                not in valid_finding_ids
            ):
                unknown_finding_ids.add(
                    finding.finding_id
                )

            for evidence_id in (
                finding.evidence_ids
            ):
                if (
                    evidence_id
                    not in valid_evidence_ids
                ):
                    unknown_evidence_ids.add(
                        evidence_id
                    )

        for recommendation in (
            report.recommendations
        ):
            for finding_id in (
                recommendation
                .related_finding_ids
            ):
                if (
                    finding_id
                    not in valid_finding_ids
                ):
                    unknown_finding_ids.add(
                        finding_id
                    )

            for evidence_id in (
                recommendation.evidence_ids
            ):
                if (
                    evidence_id
                    not in valid_evidence_ids
                ):
                    unknown_evidence_ids.add(
                        evidence_id
                    )

        for visualization in (
            report.visualizations
        ):
            if (
                visualization.evidence_id
                not in valid_evidence_ids
            ):
                unknown_evidence_ids.add(
                    visualization.evidence_id
                )

        for evidence_id in (
            report.evidence_ids_used
        ):
            if (
                evidence_id
                not in valid_evidence_ids
            ):
                unknown_evidence_ids.add(
                    evidence_id
                )

        if unknown_finding_ids:
            raise ValueError(
                "The report referenced unknown finding "
                "ID or IDs: "
                + ", ".join(
                    sorted(
                        unknown_finding_ids
                    )
                )
            )

        if unknown_evidence_ids:
            raise ValueError(
                "The report referenced unknown or "
                "unvalidated evidence ID or IDs: "
                + ", ".join(
                    sorted(
                        unknown_evidence_ids
                    )
                )
            )