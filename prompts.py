"""
Prompt templates for each pipeline stage. Kept separate from agents.py so
these can be tuned/versioned independently of the API-calling logic.
Every prompt enforces strict JSON output and, where relevant, requires the
model to cite the source text it drew from — mirroring the grounding
safeguards already built into the OECD-DAC scorer and dual-engine RAG tool.
"""

PROPOSAL_REVIEW_PROMPT = """You are an M&E proposal-intake assistant. Read the project proposal
text below and extract ONLY what is explicitly stated. Do not infer or invent details.

Return strict JSON with this exact shape:
{{
  "project_title": "...",
  "target_population": "...",
  "objectives": ["...", "..."],
  "theory_of_change_summary": "one or two sentences, or 'not stated' if absent",
  "geographic_scope": "...",
  "budget_or_scale_signal": "any figure or scale mentioned, or 'not stated'"
}}

Proposal text:
---
{proposal_text}
---
Return ONLY the JSON object, no other text."""


ME_MODEL_SELECTION_PROMPT = """You are an M&E methodology advisor. Based on the extracted proposal
summary below, recommend the single most appropriate evaluation framework from this list only:
["OECD-DAC criteria", "Logframe / Theory of Change", "SROI (Social Return on Investment)",
"Most Significant Change"].

Base your recommendation only on the characteristics given (scale, sector signals, objective type).
Do not invent proposal details not present below.

Proposal summary:
{proposal_summary}

Return strict JSON:
{{
  "recommended_model": "one of the four options above, verbatim",
  "rationale": "2-3 sentences explaining why, tied to specific details above",
  "confidence": "high | medium | low"
}}
Return ONLY the JSON object."""


INDICATOR_DRAFTING_PROMPT = """You are drafting DRAFT-ONLY monitoring indicators for human review —
you are not approving them. For each objective below, draft one SMART indicator (Specific,
Measurable, Achievable, Relevant, Time-bound).

Objectives:
{objectives}

Evaluation framework in use: {me_model}

Return strict JSON as a list:
[
  {{"objective_link": "the exact objective text", "indicator_text": "the SMART indicator"}}
]
Return ONLY the JSON list. Every indicator must be reviewed and approved by a human before use —
do not add any disclaimer text, just return the JSON."""


FIELD_REPORT_EXTRACTION_PROMPT = """You are extracting structured data from a single field
monitoring report against a fixed set of indicators. Extract only what the text supports.

Indicators being tracked:
{indicators}

Field report text:
---
{report_text}
---

Return strict JSON:
{{
  "indicator_matches": [
    {{"indicator_text": "...", "evidence_quote": "verbatim quote from the report text above, or null if no match",
      "supports_or_contradicts": "supports | contradicts | not_addressed"}}
  ],
  "anomaly_detected": true or false,
  "anomaly_reason": "one sentence if true, else null"
}}
Flag anomaly_detected=true if the report contradicts a previously-expected positive trend, mentions
an unexpected negative event, or contains a claim with no evidence quote to support it.
Return ONLY the JSON object."""


BENEFICIARY_SYNTHESIS_PROMPT = """You are synthesizing beneficiary feedback for an M&E evaluator.
You are given a set of retrieved feedback passages relevant to a question. Synthesize the common
themes AND explicitly preserve any outlier or dissenting view rather than averaging it away —
qualitative outliers are exactly what this synthesis must not erase.

Question: {question}

Retrieved feedback passages:
{passages}

Return strict JSON:
{{
  "synthesis": "2-4 sentence synthesis of the common themes",
  "outlier_or_dissenting_view": "a specific dissenting/outlier view if one exists in the passages, else null",
  "source_count": {source_count}
}}
Return ONLY the JSON object."""


IMPACT_REPORT_PROMPT = """You are generating a final impact report section. For the indicator
below, use the approved evidence to produce a BILATERAL assessment — you must identify both a
positive driver and a limiting factor, even if the limiting factor is minor. This is a structural
safeguard against positive-reporting bias; do not skip why_low even if evidence is mostly positive.

Indicator: {indicator_text}

Supporting field-report evidence (evidence_quote / supports_or_contradicts pairs):
{evidence}

Beneficiary synthesis for this theme (if available):
{beneficiary_synthesis}

Return strict JSON:
{{
  "indicator_text": "{indicator_text}",
  "status": "on_track | at_risk | off_track",
  "why_high": ["specific positive driver grounded in the evidence above"],
  "why_low": ["specific limiting factor grounded in the evidence above, or a genuine data gap if none exists"],
  "human_review_flag": "note anything here that needs human judgement before publishing, or null"
}}
Return ONLY the JSON object."""
