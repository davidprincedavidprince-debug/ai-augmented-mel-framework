"""
Agent functions — one per pipeline stage. Each function calls the Gemini
API, parses strict JSON, and returns a plain Python dict/list. No agent
here writes to the database directly and no agent's output is treated as
final — app.py is responsible for showing every output to a human for
approve/edit/reject before it moves to the next stage. That boundary is
the actual research object this demo exists to show.
"""

import os
import re
import json
import numpy as np
from dotenv import load_dotenv
from google import genai

import prompts

load_dotenv()

TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

_client = None

_STOPWORDS = set("""a an the is are was were be been being to of in on for with and or but not no
if then than that this these those it its as at by from into over under again further out up down
we you they he she i my your our their them us his her has have had do does did will would could
should can may might must""".split())

ENTAILMENT_PROMPT = """You are checking whether a beneficiary narrative supports, contradicts,
or is unrelated to a target statement describing what programme success looks like.

Pay specific attention to negation, restriction, and scope words — "only", "not", "few", "no",
"without", "except", "limited to" — since these can completely flip a claim's meaning even when
the narrative shares heavy topical overlap with the target (same subject matter, opposite claim).

Target: "{target}"

Narrative: "{narrative}"

Does the narrative describe the target being ACHIEVED (supports), CONTRADICTED — for example by
describing exclusion, restriction to a subgroup, or the opposite of the target despite similar
topic — or is it UNRELATED/neutral to the target?

Return strict JSON:
{{"verdict": "supports" | "contradicts" | "unrelated", "reasoning": "one sentence; quote the specific restriction or negation word if that is what drives the verdict"}}
Return ONLY the JSON object, no other text."""


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        _client = genai.Client(api_key=api_key)
    return _client


def _generate_json(prompt_text):
    """Calls Gemini, strips markdown code fences if present, parses JSON."""
    client = get_client()
    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt_text)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def embed_text(text):
    """Returns a plain list of floats for the given text."""
    client = get_client()
    result = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return list(result.embeddings[0].values)


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def _tokenize(text):
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return set(w for w in words if w not in _STOPWORDS and len(w) > 2)


def lexical_similarity(text_a, text_b):
    """Jaccard similarity of stopword-filtered word sets. Deliberately naive —
    this is the 'just count matching keywords' baseline, included specifically
    to demonstrate where it disagrees with semantic (embedding) similarity."""
    set_a, set_b = _tokenize(text_a), _tokenize(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def check_entailment(target_description, narrative_text):
    """A narrow, targeted LLM call — NOT a generative summarizer, and it never
    decides anything on its own. It returns one more signal (like the lexical
    score) for a human to weigh alongside the embedding similarity score."""
    prompt = ENTAILMENT_PROMPT.format(target=target_description, narrative=narrative_text)
    return _generate_json(prompt)


def combined_verdict(semantic_score, threshold, entailment_result):
    """Combines the cheap-but-unreliable cosine similarity signal with the
    slower-but-more-accurate LLM entailment check. Entailment, when available,
    OVERRIDES the raw threshold for 'supports' and 'contradicts' — those are
    exactly the cases (agreement despite low word overlap, negation despite
    high similarity) cosine similarity is worst at. 'unrelated' verdicts, or
    entries not yet checked, fall back to the semantic threshold."""
    if entailment_result:
        verdict = entailment_result.get("verdict")
        if verdict == "contradicts":
            return "divergent"
        if verdict == "supports":
            return "aligned"
    return "divergent" if semantic_score < threshold else "aligned"


def score_feedback_against_indicator(indicator_embedding, indicator_text, feedback_rows):
    """feedback_rows: list of dicts with 'feedback_text' and 'embedding' (JSON string).
    Returns the list with 'semantic_score', 'lexical_score', and 'gap' added to
    each, sorted by semantic_score ascending (most divergent first, by the
    embedding's own — imperfect — judgement)."""
    scored = []
    for row in feedback_rows:
        emb = json.loads(row["embedding"])
        semantic = cosine_similarity(indicator_embedding, emb)
        lexical = lexical_similarity(indicator_text, row["feedback_text"])
        row_copy = dict(row)
        row_copy["semantic_score"] = semantic
        row_copy["lexical_score"] = lexical
        row_copy["gap"] = semantic - lexical
        scored.append(row_copy)
    scored.sort(key=lambda r: r["semantic_score"])
    return scored


# ---------- Stage 1: Proposal review ----------

def review_proposal(proposal_text):
    prompt = prompts.PROPOSAL_REVIEW_PROMPT.format(proposal_text=proposal_text)
    return _generate_json(prompt)


# ---------- Stage 2: M&E model selection ----------

def select_me_model(proposal_summary_json):
    prompt = prompts.ME_MODEL_SELECTION_PROMPT.format(
        proposal_summary=json.dumps(proposal_summary_json, indent=2)
    )
    return _generate_json(prompt)


# ---------- Stage 3: Indicator drafting ----------

def draft_indicators(objectives, me_model):
    prompt = prompts.INDICATOR_DRAFTING_PROMPT.format(
        objectives="\n".join(f"- {o}" for o in objectives),
        me_model=me_model,
    )
    return _generate_json(prompt)


# ---------- Stage 4: Continuous monitoring / field report extraction ----------

def extract_field_report(report_text, approved_indicators):
    indicator_lines = "\n".join(f"- {i['indicator_text']}" for i in approved_indicators)
    prompt = prompts.FIELD_REPORT_EXTRACTION_PROMPT.format(
        indicators=indicator_lines, report_text=report_text
    )
    return _generate_json(prompt)


# ---------- Stage 5: Beneficiary evaluation (retrieval + synthesis) ----------

def retrieve_relevant_feedback(question, feedback_rows, top_k=5):
    """feedback_rows: list of dicts with 'feedback_text' and 'embedding' (JSON string)."""
    if not feedback_rows:
        return []
    q_embedding = embed_text(question)
    scored = []
    for row in feedback_rows:
        emb = json.loads(row["embedding"])
        score = cosine_similarity(q_embedding, emb)
        scored.append((score, row["feedback_text"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:top_k]]


def synthesize_beneficiary_feedback(question, passages):
    passages_block = "\n".join(f"- {p}" for p in passages) if passages else "(no matching passages)"
    prompt = prompts.BENEFICIARY_SYNTHESIS_PROMPT.format(
        question=question, passages=passages_block, source_count=len(passages)
    )
    return _generate_json(prompt)


# ---------- Dynamic demo data generation (grounded in real approved indicators) ----------

def generate_demo_field_reports(approved_indicators):
    indicator_lines = "\n".join(f"- {i['indicator_text']}" for i in approved_indicators)
    prompt = prompts.GENERATE_FIELD_REPORTS_PROMPT.format(indicators=indicator_lines)
    result = _generate_json(prompt)
    return result["field_reports"]


def generate_demo_beneficiary_feedback(approved_indicators):
    indicator_lines = "\n".join(f"- {i['indicator_text']}" for i in approved_indicators)
    prompt = prompts.GENERATE_BENEFICIARY_FEEDBACK_PROMPT.format(indicators=indicator_lines)
    result = _generate_json(prompt)
    return result["beneficiary_feedback"]


# ---------- Stage 6: Impact report generation ----------

def generate_impact_report_section(indicator_text, evidence_list, beneficiary_synthesis_text):
    evidence_block = "\n".join(
        f"- {e.get('evidence_quote', 'none')} ({e.get('supports_or_contradicts', 'n/a')})"
        for e in evidence_list
    ) if evidence_list else "(no field-report evidence collected yet)"
    prompt = prompts.IMPACT_REPORT_PROMPT.format(
        indicator_text=indicator_text,
        evidence=evidence_block,
        beneficiary_synthesis=beneficiary_synthesis_text or "(none available)",
    )
    return _generate_json(prompt)
