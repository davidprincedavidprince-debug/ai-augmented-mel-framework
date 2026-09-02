# Hybrid Human-AI M&E Pipeline — Demo

A six-stage prototype of a hybrid human-AI framework for continuous impact
monitoring, built to accompany a PhD research proposal on AI-assisted M&E
in resource-constrained development organisations.

**The point of this demo is not the AI.** Every stage is designed so the AI
only ever *drafts* — a human must approve, edit, or reject before the
output can be used by the next stage. That approve/edit/reject boundary is
the actual research object: the proposal's RQ2 asks exactly where this line
should sit, and this app makes that boundary a clickable thing instead of
an abstract claim.

## Pipeline stages

| Stage | Agent | Human retains |
|---|---|---|
| 1. Proposal review | Extracts objectives, target population, theory of change | Reviews extraction accuracy |
| 2. M&E model selection | Recommends OECD-DAC / Logframe / SROI / MSC | Confirms or overrides |
| 3. Indicator identification | Drafts SMART indicators per objective | Approves / edits / rejects each one |
| 4. Continuous monitoring | Extracts indicator evidence from field reports, flags anomalies | Reviews every flagged anomaly |
| 5. Beneficiary evaluation | Retrieves + synthesizes feedback, preserves dissenting views | Reads raw retrieved passages, not just synthesis |
| 6. Impact report | Generates bilateral (why_high / why_low) assessment per indicator | Reviews every human_review_flag before publishing |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your Gemini API key from https://aistudio.google.com/apikey
streamlit run app.py
```

## Deploying for free (so it works from any device, including for the call)

1. Push this folder to a GitHub repository.
2. Go to https://share.streamlit.io, sign in with GitHub, and deploy this repo.
3. Add `GEMINI_API_KEY` (and optionally `GEMINI_TEXT_MODEL`, `GEMINI_EMBED_MODEL`)
   under the app's **Settings → Secrets** in the Streamlit Cloud dashboard —
   never commit your real key to the repo.
4. Streamlit Cloud gives you a public URL you can open on any device,
   including on the call itself, with no local setup needed.

Note: Streamlit Community Cloud's filesystem is ephemeral, so the SQLite
file resets on redeploy/restart. That's fine for a live demo — click
**Load demo scenario** in the sidebar at the start of each session to
repopulate it in one click. For anything you want to persist long-term,
swap `database.py`'s `DB_PATH` for a hosted free-tier Postgres (e.g.
Supabase or Neon) — the SQL in `database.py` is close to standard enough
that only the connection line would need to change.

## Files

- `app.py` — Streamlit UI, one tab per pipeline stage, all approve/edit/reject logic
- `agents.py` — Gemini API calls, one function per stage
- `prompts.py` — prompt templates, kept separate so they're easy to tune
- `database.py` — SQLite schema and all read/write helpers
- `sample_data.py` — demo proposal, field reports, and beneficiary feedback for a reliable live demo
- `requirements.txt`, `.env.example`, `.gitignore` — setup files

## Known limitations (worth stating out loud in a PhD interview, not hiding)

- Anomaly detection in stage 4 is LLM judgement, not a validated statistical
  method — flagged explicitly as a Phase 3 research question, not a solved
  problem.
- Retrieval in stage 5 uses Gemini embeddings + cosine similarity in plain
  Python/NumPy rather than a dedicated vector database — fine at demo scale
  (a handful of feedback entries), not tested at the volume a real
  organisation's reporting would produce.
- No independent human-coded validation of any stage's output yet — that is
  precisely what the doctoral research proposes to build and test.
