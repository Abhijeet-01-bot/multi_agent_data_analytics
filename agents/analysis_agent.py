from __future__ import annotations

from typing import Protocol

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from config.llm import create_llm
from prompts.analysis_prompt import (
    ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_prompt,
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
from config.settings import settings



class StructuredAnalysisModel(Protocol):
    def invoke(
        self,
        input: object,
    ) -> AnalysisResult:
        ...


class AnalysisAgent:
    """
    Interpret validated evidence without calculating or
    inventing new facts.
    """

    def __init__(
        self,
        structured_model: (
            StructuredAnalysisModel | None
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
                structured_model = (
                    llm.with_structured_output(
                        AnalysisResult.model_json_schema(),
                        method="json_schema",
                    )
                )
            else:
                structured_model = (
                    llm.with_structured_output(
                        AnalysisResult,
                        method="json_schema",
                    )
                )

        self.structured_model = structured_model

    def analyze(
        self,
        intent: IntentResult,
        plan: ExecutionPlan,
        evidence_bundle: EvidenceBundle,
    ) -> AnalysisResult:
        if intent.clarification_required:
            raise ValueError(
                "Analysis cannot start while the "
                "intent requires clarification."
            )

        if intent.unsupported_request:
            raise ValueError(
                "Analysis cannot start for an "
                "unsupported request."
            )

        if not evidence_bundle.records:
            raise ValueError(
                "Analysis requires at least one "
                "evidence record."
            )

        if (
            evidence_bundle.validated_record_count
            == 0
        ):
            raise ValueError(
                "Analysis requires at least one "
                "validated evidence record."
            )

        prompt = build_analysis_user_prompt(
            intent=intent,
            plan=plan,
            evidence_bundle=evidence_bundle,
        )

        messages = [
            SystemMessage(
                content=ANALYSIS_SYSTEM_PROMPT
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
            AnalysisResult,
        ):
            analysis_data = raw_result.model_dump(
                mode="json"
            )

        elif isinstance(
            raw_result,
            dict,
        ):
            analysis_data = dict(raw_result)

        elif hasattr(
            raw_result,
            "model_dump",
        ):
            analysis_data = raw_result.model_dump(
                mode="json"
            )

        else:
            raise TypeError(
                "The Analysis Agent returned an "
                "unsupported result type: "
                f"{type(raw_result).__name__}"
            )

        normalized_data = (
            self._normalize_analysis_data(
                analysis_data=analysis_data,
                evidence_bundle=(
                    evidence_bundle
                ),
            )
        )

        result = AnalysisResult.model_validate(
            normalized_data
        )

        self._validate_evidence_references(
            result=result,
            evidence_bundle=evidence_bundle,
        )

        return result

    @staticmethod
    def _validate_evidence_references(
        result: AnalysisResult,
        evidence_bundle: EvidenceBundle,
    ) -> None:
        """
        Ensure the model references only evidence records
        that actually exist.
        """

        valid_evidence_ids = {
            record.evidence_id
            for record in evidence_bundle.records
        }

        unknown_ids: set[str] = set()

        for finding in result.findings:
            for evidence_id in finding.evidence_ids:
                if (
                    evidence_id
                    not in valid_evidence_ids
                ):
                    unknown_ids.add(evidence_id)

        if unknown_ids:
            raise ValueError(
                "Analysis referenced unknown evidence "
                "ID or IDs: "
                + ", ".join(
                    sorted(unknown_ids)
                )
            )

    @staticmethod
    def _normalize_analysis_data(
        analysis_data: dict,
        evidence_bundle: EvidenceBundle,
    ) -> dict:
        """
        Normalize predictable local-model omissions while
        preserving evidence-grounding requirements.
        """

        normalized = dict(
            analysis_data
        )

        normalized.setdefault(
            "analysis_summary",
            (
                "The validated evidence was analyzed."
            ),
        )

        normalized.setdefault(
            "findings",
            [],
        )

        normalized.setdefault(
            "evidence_sufficient",
            False,
        )

        normalized.setdefault(
            "unanswered_questions",
            [],
        )

        normalized.setdefault(
            "additional_tasks",
            [],
        )

        normalized.setdefault(
            "limitations",
            [],
        )

        normalized.setdefault(
            "warnings",
            [],
        )

        normalized.setdefault(
            "confidence",
            0.5,
        )

        valid_evidence_ids = [
            record.evidence_id
            for record
            in evidence_bundle.records
            if record.validated
        ]

        # When exactly one validated evidence record exists,
        # replace generic local-model identifiers such as
        # "data" with the actual evidence ID.
        if len(valid_evidence_ids) == 1:
            only_evidence_id = (
                valid_evidence_ids[0]
            )

            generic_evidence_ids = {
                "data",
                "evidence",
                "result",
                "results",
                "query",
                "query_result",
                "calculation",
                "calculation_result",
                "source",
            }

            for finding in normalized[
                "findings"
            ]:
                if not isinstance(
                    finding,
                    dict,
                ):
                    continue

                finding_ids = finding.get(
                    "evidence_ids",
                    [],
                )

                # Missing evidence references can be
                # repaired when exactly one validated
                # record exists.
                if not finding_ids:
                    finding[
                        "evidence_ids"
                    ] = [
                        only_evidence_id
                    ]

                    continue

                normalized_finding_ids = {
                    str(evidence_id)
                    .strip()
                    .lower()
                    for evidence_id
                    in finding_ids
                }

                # Repair only generic placeholders
                # commonly emitted by small local models.
                #
                # A specific unknown identifier such as
                # E-UNKNOWN-999 must remain unchanged so
                # _validate_evidence_references() rejects it.
                if (
                    normalized_finding_ids
                    and normalized_finding_ids
                    .issubset(
                        generic_evidence_ids
                    )
                ):
                    finding[
                        "evidence_ids"
                    ] = [
                        only_evidence_id
                    ]

        if (
            not normalized[
                "evidence_sufficient"
            ]
            and not normalized[
                "unanswered_questions"
            ]
            and not normalized[
                "additional_tasks"
            ]
        ):
            normalized[
                "unanswered_questions"
            ] = [
                (
                    "What additional validated evidence "
                    "is required to fully answer the "
                    "business question?"
                )
            ]

        return normalized