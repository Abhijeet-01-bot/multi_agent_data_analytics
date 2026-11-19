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
from schemas.intent_schemas import IntentResult
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
                # Passing a JSON schema dictionary avoids
                # immediate Pydantic parsing inside
                # LangChain. We normalize the dictionary
                # before validating it ourselves.
                structured_model = (
                    llm.with_structured_output(
                        ExecutiveReport.model_json_schema(),
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

        self.structured_model = structured_model

    def create_report(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        analysis: AnalysisResult,
        evidence_bundle: EvidenceBundle,
    ) -> ExecutiveReport:
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
            evidence_bundle.validated_record_count
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

        raw_result = self.structured_model.invoke(
            messages
        )

        if isinstance(
            raw_result,
            ExecutiveReport,
        ):
            report = raw_result

        else:
            normalized_result = (
                self._normalize_report_data(
                    report_data=raw_result,
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
        Return available tabular fields from the
        referenced evidence record.
        """

        evidence = next(
            (
                record
                for record
                in evidence_bundle.records
                if (
                    record.evidence_id
                    == evidence_id
                )
            ),
            None,
        )

        if evidence is None:
            return []

        rows = evidence.source_rows

        if not rows:
            records = (
                evidence
                .calculation_output
                .get(
                    "records",
                    [],
                )
            )

            if isinstance(records, list):
                rows = [
                    record
                    for record in records
                    if isinstance(
                        record,
                        dict,
                    )
                ]

        return sorted(
            {
                field_name
                for row in rows
                for field_name in row.keys()
            }
        )

    @classmethod
    def _normalize_visualization(
        cls,
        visualization: dict[str, Any],
        evidence_bundle: EvidenceBundle,
    ) -> dict[str, Any]:
        """
        Repair only predictable field omissions.

        The method does not invent numerical data.
        It maps available evidence fields into chart
        roles when the mapping is unambiguous.
        """

        normalized = dict(visualization)

        chart_type = normalized.get(
            "chart_type"
        )

        evidence_id = normalized.get(
            "evidence_id",
            "",
        )

        available_fields = (
            cls._get_evidence_fields(
                evidence_id=evidence_id,
                evidence_bundle=(
                    evidence_bundle
                ),
            )
        )

        ranking_label_candidates = [
            "label",
            "CategoryName",
            "ProductName",
            "CustomerName",
        ]

        ranking_value_candidates = [
            "value",
            "NetRevenue",
            "GrossRevenue",
            "OrderCount",
            "ProductQuantity",
        ]

        label_field = next(
            (
                field
                for field
                in ranking_label_candidates
                if field in available_fields
            ),
            None,
        )

        value_field = next(
            (
                field
                for field
                in ranking_value_candidates
                if field in available_fields
            ),
            None,
        )

        if chart_type == "horizontal_bar":
            if not normalized.get("x_field"):
                normalized["x_field"] = (
                    value_field
                )

            if not normalized.get("y_field"):
                normalized["y_field"] = (
                    label_field
                )

        elif chart_type == "bar":
            if not normalized.get("x_field"):
                normalized["x_field"] = (
                    label_field
                )

            if not normalized.get("y_field"):
                normalized["y_field"] = (
                    value_field
                )

        elif chart_type == "kpi":
            if not normalized.get(
                "value_field"
            ):
                normalized["value_field"] = (
                    value_field
                )

                if (
                    normalized["value_field"]
                    is None
                    and len(
                        available_fields
                    )
                    == 1
                ):
                    normalized[
                        "value_field"
                    ] = available_fields[0]

        elif chart_type == "line":
            if not normalized.get("x_field"):
                time_candidates = [
                    "OrderMonth",
                    "order_month",
                    "Month",
                    "Date",
                    "OrderDate",
                ]

                normalized["x_field"] = next(
                    (
                        field
                        for field
                        in time_candidates
                        if field
                        in available_fields
                    ),
                    None,
                )

            if not normalized.get("y_field"):
                normalized["y_field"] = (
                    value_field
                )

        # Remove null values only when they are not
        # required for the selected chart. Required-field
        # validation remains the responsibility of the
        # Pydantic VisualizationSpec model.
        return normalized
    
    @classmethod
    def _build_fallback_visualization(
        cls,
        evidence_bundle: EvidenceBundle,
    ) -> dict[str, Any] | None:
        """
        Build a conservative chart when the local model
        omits visualizations.

        A chart is created only when the evidence fields
        provide an unambiguous mapping.
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

            field_set = set(fields)

            if {
                "label",
                "value",
            }.issubset(field_set):
                return {
                    "visualization_id": (
                        "V-AUTO-1"
                    ),
                    "chart_type": (
                        "horizontal_bar"
                    ),
                    "title": (
                        "Category Revenue Ranking"
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
                    "sort_order": "descending",
                    "top_n": None,
                    "x_axis_title": "Net Revenue",
                    "y_axis_title": "Category",
                    "show_values": True,
                    "metadata": {
                        "generated_by": (
                            "deterministic_fallback"
                        )
                    },
                }

            numeric_candidates = [
                "OrderCount",
                "NetRevenue",
                "GrossRevenue",
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

            if (
                numeric_field
                and len(
                    evidence.source_rows
                )
                == 1
            ):
                return {
                    "visualization_id": (
                        "V-AUTO-1"
                    ),
                    "chart_type": "kpi",
                    "title": numeric_field,
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

        This method does not invent business values. It
        derives references and visualization roles from
        validated evidence already supplied to the model.
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

        visualizations = (
            normalized_report.get(
                "visualizations"
            )
            or []
        )

        normalized_visualizations = [
            cls._normalize_visualization(
                visualization=visualization,
                evidence_bundle=(
                    evidence_bundle
                ),
            )
            for visualization
            in visualizations
            if isinstance(
                visualization,
                dict,
            )
        ]

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

                warnings = list(
                    normalized_report.get(
                        "warnings",
                        [],
                    )
                )

                warnings.append(
                    "A deterministic visualization "
                    "specification was generated because "
                    "the local model did not provide one."
                )

                normalized_report[
                    "warnings"
                ] = warnings

        normalized_report[
            "visualizations"
        ] = normalized_visualizations

        referenced_evidence_ids: set[str] = set()

        for finding in normalized_report[
            "findings"
        ]:
            if isinstance(finding, dict):
                referenced_evidence_ids.update(
                    finding.get(
                        "evidence_ids",
                        [],
                    )
                )

        for recommendation in normalized_report[
            "recommendations"
        ]:
            if isinstance(
                recommendation,
                dict,
            ):
                referenced_evidence_ids.update(
                    recommendation.get(
                        "evidence_ids",
                        [],
                    )
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