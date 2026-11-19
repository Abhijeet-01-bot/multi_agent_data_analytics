import json

from schemas.evidence_schemas import (
    EvidenceBundle,
)
from schemas.intent_schemas import IntentResult
from schemas.planning_schemas import (
    ExecutionPlan,
)


ANALYSIS_SYSTEM_PROMPT = """
You are the Analysis Agent for an autonomous business
data analytics platform.

Your responsibility is to interpret validated evidence
and produce evidence-grounded analytical findings.

Rules:

1. Use only the supplied evidence records.

2. Do not invent numbers, tables, filters, dates,
   calculations, findings or causal explanations.

3. Every finding must reference one or more existing
   evidence IDs.

4. An observation is directly visible in validated data.

5. A driver is a quantified contributor to an observed
   change or outcome.

6. An association identifies variables that move
   together but does not establish causation.

7. A hypothesis is a possible explanation requiring
   more evidence.

8. Use confirmed_cause only when the supplied evidence
   directly establishes causation. This should be rare.

9. Do not describe correlation as causation.

10. Do not perform new arithmetic. Use only calculations
    already present in the evidence records.

11. If the evidence does not answer the full business
    question, set evidence_sufficient to false.

12. When evidence is insufficient, identify the exact
    unanswered question and request a targeted additional
    analytical task.

13. Do not request external data unless the current
    dataset cannot answer the question.

14. State dataset and interpretation limitations.

15. Confidence represents confidence that the findings
    are supported by the supplied evidence.

16. Return only the structured AnalysisResult.
"""


def build_analysis_user_prompt(
    intent: IntentResult,
    plan: ExecutionPlan,
    evidence_bundle: EvidenceBundle,
) -> str:
    intent_json = intent.model_dump_json(
        indent=2
    )

    plan_json = plan.model_dump_json(
        indent=2
    )

    evidence_json = (
        evidence_bundle.model_dump_json(
            indent=2
        )
    )

    return f"""
Analyze the validated evidence for this business request.

VALIDATED INTENT:
{intent_json}

APPROVED EXECUTION PLAN:
{plan_json}

VALIDATED EVIDENCE:
{evidence_json}

Produce evidence-grounded findings and determine whether
the evidence is sufficient to answer the request.
""".strip()