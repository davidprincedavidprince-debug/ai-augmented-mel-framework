"""
Hybrid Human-AI M&E Pipeline — demo app.
Six stages, one Streamlit app, one SQLite file. Every AI output requires a
human action (approve / edit / reject) before it becomes usable input to
the next stage — that boundary, not the AI itself, is what this demo exists
to make visible.

Run locally:  streamlit run app.py
"""

import json
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF

import database as db
import agents
import sample_data

st.set_page_config(page_title="Hybrid Human-AI M&E Pipeline", layout="wide")
db.init_db()


def extract_text_from_upload(uploaded_file):
    """Returns plain text from an uploaded PDF or .txt file."""
    uploaded_file.seek(0)
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    return uploaded_file.read().decode("utf-8", errors="ignore").strip()

if "proposal_id" not in st.session_state:
    st.session_state.proposal_id = None

st.title("Hybrid Human-AI M&E Pipeline — demo")
st.caption(
    "AI drafts. A human approves, edits, or rejects at every stage boundary before "
    "anything moves forward. Nothing here auto-publishes."
)

with st.sidebar:
    st.header("Session")
    if st.button("Load demo scenario", use_container_width=True):
        extracted = agents.review_proposal(sample_data.SAMPLE_PROPOSAL)
        pid = db.insert_proposal(sample_data.SAMPLE_PROPOSAL, extracted)
        st.session_state.proposal_id = pid
        st.success(f"Demo proposal loaded (id {pid})")

    if st.button("Reset all data", use_container_width=True, type="secondary"):
        db.reset_db()
        for key in ["proposal_id", "me_rec", "last_synthesis", "last_upload_name", "proposal_text_area"]:
            st.session_state.pop(key, None)
        st.success("All data cleared — starting fresh.")
        st.rerun()

    proposals = db.list_proposals()
    if proposals:
        options = {f"#{p['id']} — {p['created_at'][:19]}": p["id"] for p in proposals}
        choice = st.selectbox("Active proposal", list(options.keys()))
        st.session_state.proposal_id = options[choice]

pid = st.session_state.proposal_id
tabs = st.tabs([
    "1. Proposal review",
    "2. M&E model",
    "3. Indicators",
    "4. Monitoring",
    "5. Beneficiary voice",
    "6. Impact report",
])

# ---------------- Stage 1 ----------------
with tabs[0]:
    st.subheader("Stage 1 — Proposal review agent")

    uploaded_file = st.file_uploader("Upload the actual proposal (PDF or .txt)", type=["pdf", "txt"])
    if uploaded_file is not None and st.session_state.get("last_upload_name") != uploaded_file.name:
        st.session_state.proposal_text_area = extract_text_from_upload(uploaded_file)
        st.session_state.last_upload_name = uploaded_file.name

    proposal_text = st.text_area(
        "Proposal text — auto-filled from upload above; edit freely, or paste/type directly instead",
        height=250,
        key="proposal_text_area",
    )

    if st.button("Run extraction") and proposal_text.strip():
        with st.spinner("Extracting..."):
            extracted = agents.review_proposal(proposal_text)
        pid = db.insert_proposal(proposal_text, extracted)
        st.session_state.proposal_id = pid
        st.rerun()

    if pid:
        proposal = db.get_proposal(pid)
        extracted = json.loads(proposal["extracted_json"])
        st.json(extracted)
        st.info("Human checkpoint: review the extracted fields above before proceeding to stage 2.")

# ---------------- Stage 2 ----------------
with tabs[1]:
    st.subheader("Stage 2 — M&E model selection agent")
    if not pid:
        st.warning("Complete stage 1 first.")
    else:
        proposal = db.get_proposal(pid)
        extracted = json.loads(proposal["extracted_json"])
        if st.button("Get model recommendation"):
            with st.spinner("Analysing..."):
                rec = agents.select_me_model(extracted)
            st.session_state.me_rec = rec

        rec = st.session_state.get("me_rec")
        if rec:
            st.write(f"**Recommended:** {rec['recommended_model']}  (confidence: {rec['confidence']})")
            st.write(rec["rationale"])

        options = ["OECD-DAC criteria", "Logframe / Theory of Change",
                   "SROI (Social Return on Investment)", "Most Significant Change"]
        default_idx = options.index(rec["recommended_model"]) if rec and rec["recommended_model"] in options else 0
        final_choice = st.selectbox("Human decision — confirm or override", options, index=default_idx)
        if st.button("Confirm M&E model"):
            db.set_me_model_choice(pid, final_choice, rec["rationale"] if rec else "human override, no AI rationale")
            st.success(f"M&E model set to: {final_choice}")

# ---------------- Stage 3 ----------------
with tabs[2]:
    st.subheader("Stage 3 — Indicator identification agent")
    if not pid:
        st.warning("Complete stages 1-2 first.")
    else:
        proposal = db.get_proposal(pid)
        extracted = json.loads(proposal["extracted_json"])
        me_model = proposal["me_model_choice"] or "Logframe / Theory of Change"

        if st.button("Draft indicators"):
            with st.spinner("Drafting..."):
                drafted = agents.draft_indicators(extracted["objectives"], me_model)
            db.insert_indicators(pid, drafted)
            st.rerun()

        indicators = db.get_indicators(pid)
        if indicators:
            st.write("Review each draft indicator — approve, edit, or reject:")
            for ind in indicators:
                cols = st.columns([5, 1, 1, 1])
                new_text = cols[0].text_input(
                    f"Indicator #{ind['id']}", value=ind["indicator_text"], key=f"txt_{ind['id']}",
                    label_visibility="collapsed"
                )
                if cols[1].button("Approve", key=f"appr_{ind['id']}"):
                    db.update_indicator_status(ind["id"], "approved", new_text)
                    st.rerun()
                if cols[2].button("Edit & save", key=f"edit_{ind['id']}"):
                    db.update_indicator_status(ind["id"], "edited", new_text)
                    st.rerun()
                if cols[3].button("Reject", key=f"rej_{ind['id']}"):
                    db.update_indicator_status(ind["id"], "rejected", new_text)
                    st.rerun()
                st.caption(f"Status: {ind['status']} — linked objective: {ind['objective_link']}")

# ---------------- Stage 4 ----------------
with tabs[3]:
    st.subheader("Stage 4 — Continuous monitoring agent")
    if not pid:
        st.warning("Complete stages 1-3 first.")
    else:
        approved = [i for i in db.get_indicators(pid) if i["status"] in ("approved", "edited")]
        if not approved:
            st.warning("No approved indicators yet — approve at least one in stage 3.")
        else:
            col_a, col_b = st.columns(2)
            if col_a.button("🎲 Generate demo field reports for THIS proposal (AI)"):
                with st.spinner("Generating field reports grounded in your approved indicators..."):
                    generated = agents.generate_demo_field_reports(approved)
                for report_text in generated:
                    result = agents.extract_field_report(report_text, approved)
                    db.insert_field_report(
                        pid, report_text, result,
                        result.get("anomaly_detected", False), result.get("anomaly_reason")
                    )
                st.rerun()
            if col_b.button("Load fixed demo field reports (farmer livelihoods scenario)"):
                for report_text in sample_data.SAMPLE_FIELD_REPORTS:
                    result = agents.extract_field_report(report_text, approved)
                    db.insert_field_report(
                        pid, report_text, result,
                        result.get("anomaly_detected", False), result.get("anomaly_reason")
                    )
                st.rerun()

            new_report = st.text_area("Or paste a new field report")
            if st.button("Process field report") and new_report.strip():
                with st.spinner("Extracting against approved indicators..."):
                    result = agents.extract_field_report(new_report, approved)
                db.insert_field_report(
                    pid, new_report, result,
                    result.get("anomaly_detected", False), result.get("anomaly_reason")
                )
                st.rerun()

            reports = db.get_field_reports(pid)
            for r in reports:
                extracted = json.loads(r["extracted_json"])
                flag = "🔴 ANOMALY" if r["anomaly_flag"] else "🟢 clear"
                with st.expander(f"{flag} — report #{r['id']}"):
                    st.write(r["report_text"])
                    if r["anomaly_flag"]:
                        st.error(r["anomaly_reason"])
                    st.json(extracted)

# ---------------- Stage 5 ----------------
with tabs[4]:
    st.subheader("Stage 5 — Beneficiary evaluation agent")
    if not pid:
        st.warning("Complete stage 1 first.")
    else:
        st.markdown("### 5a. Collect beneficiary voice")

        approved_for_gen = [i for i in db.get_indicators(pid) if i["status"] in ("approved", "edited")]
        col_a, col_b = st.columns(2)
        if approved_for_gen:
            if col_a.button("🎲 Generate demo beneficiary feedback for THIS proposal (AI)"):
                with st.spinner("Generating feedback grounded in your approved indicators..."):
                    generated = agents.generate_demo_beneficiary_feedback(approved_for_gen)
                    for text in generated:
                        emb = agents.embed_text(text)
                        db.insert_feedback(pid, text, emb)
                st.success(f"Generated and embedded {len(generated)} feedback entries.")
        else:
            col_a.caption("Approve at least one indicator in stage 3 to generate matching feedback.")

        if col_b.button("Load fixed demo feedback (farmer livelihoods scenario)"):
            with st.spinner("Embedding feedback..."):
                for text in sample_data.SAMPLE_BENEFICIARY_FEEDBACK:
                    emb = agents.embed_text(text)
                    db.insert_feedback(pid, text, emb)
            st.success("Demo feedback loaded and embedded.")

        new_feedback = st.text_input("Or add a beneficiary feedback entry")
        if st.button("Add feedback") and new_feedback.strip():
            emb = agents.embed_text(new_feedback)
            db.insert_feedback(pid, new_feedback, emb)
            st.rerun()

        feedback_rows = db.get_feedback(pid)
        st.caption(f"{len(feedback_rows)} feedback entries stored.")

        st.divider()
        st.markdown("### 5b. Divergence review — beneficiary voice vs. indicator")
        st.caption(
            "Every feedback entry is compared against a chosen indicator with both a lexical "
            "(keyword-overlap) and semantic (embedding) score, then an LLM entailment check runs "
            "automatically on each — that entailment verdict, not raw cosine similarity, drives "
            "the red/green flag. Nothing is recorded as confirmed until a human acts on it below."
        )

        approved_for_review = [i for i in db.get_indicators(pid) if i["status"] in ("approved", "edited")]
        if not approved_for_review:
            st.warning("Approve at least one indicator in stage 3 first.")
        elif not feedback_rows:
            st.warning("Add beneficiary feedback above first.")
        else:
            ind_options = {i["indicator_text"]: i for i in approved_for_review}
            sel_ind_text = st.selectbox("Indicator to review against", list(ind_options.keys()))
            indicator = ind_options[sel_ind_text]

            if not indicator.get("indicator_text_embedding"):
                with st.spinner("Embedding indicator text (first time only)..."):
                    emb = agents.embed_text(indicator["indicator_text"])
                db.set_indicator_embedding(indicator["id"], emb)
                indicator["indicator_text_embedding"] = json.dumps(emb)

            indicator_embedding = json.loads(indicator["indicator_text_embedding"])
            scored = agents.score_feedback_against_indicator(
                indicator_embedding, indicator["indicator_text"], feedback_rows
            )

            # Auto-run entailment for every entry not already cached — no
            # per-entry clicking required. Cached in session_state so it only
            # calls the API once per (indicator, entry) pair per session.
            uncached = [
                r for r in scored
                if f"dissonance_entail_{indicator['id']}_{r['id']}" not in st.session_state
            ]
            if uncached:
                progress = st.progress(0.0, text=f"Checking {len(uncached)} entries against the indicator...")
                for i, row in enumerate(uncached):
                    result = agents.check_entailment(indicator["indicator_text"], row["feedback_text"])
                    st.session_state[f"dissonance_entail_{indicator['id']}_{row['id']}"] = result
                    progress.progress((i + 1) / len(uncached))
                progress.empty()

            st.markdown("**Lexical vs. semantic comparison**")
            compare_df = pd.DataFrame([
                {
                    "entry": (r["feedback_text"][:70] + "...") if len(r["feedback_text"]) > 70 else r["feedback_text"],
                    "semantic_score": round(r["semantic_score"], 3),
                    "lexical_score": round(r["lexical_score"], 3),
                    "gap": round(r["gap"], 3),
                }
                for r in scored
            ])
            compare_df["abs_gap"] = compare_df["gap"].abs()
            compare_df = compare_df.sort_values("abs_gap", ascending=False).drop(columns="abs_gap")
            st.dataframe(compare_df, width="stretch")

            st.markdown("**Divergence result (LLM entailment — primary signal)**")
            llm_divergent, llm_aligned = 0, 0
            for row in scored:
                cached = st.session_state.get(f"dissonance_entail_{indicator['id']}_{row['id']}")
                verdict = agents.combined_verdict(row["semantic_score"], 0.70, cached)
                if verdict == "divergent":
                    llm_divergent += 1
                else:
                    llm_aligned += 1
            c1, c2 = st.columns(2)
            c1.metric("🔴 Flagged as divergent", llm_divergent)
            c2.metric("🟢 Treated as aligned", llm_aligned)

            with st.expander("Reference only: raw cosine similarity threshold (not used for the flags above)"):
                threshold = st.slider(
                    "Cosine similarity threshold (reference only)",
                    min_value=0.0, max_value=1.0, value=0.70, step=0.01,
                    key=f"dissonance_threshold_{indicator['id']}",
                )
                cosine_divergent = [r for r in scored if r["semantic_score"] < threshold]
                cosine_aligned = [r for r in scored if r["semantic_score"] >= threshold]
                c3, c4 = st.columns(2)
                c3.metric("Flagged as divergent (cosine only)", len(cosine_divergent))
                c4.metric("Treated as aligned (cosine only)", len(cosine_aligned))
                score_df = pd.DataFrame({"semantic_score": [r["semantic_score"] for r in scored]})
                st.bar_chart(score_df["semantic_score"].sort_values(ascending=True).reset_index(drop=True))

            st.divider()
            for row in scored:
                cached = st.session_state.get(f"dissonance_entail_{indicator['id']}_{row['id']}")
                verdict = agents.combined_verdict(row["semantic_score"], threshold, cached)
                flag = "🔴 divergent" if verdict == "divergent" else "🟢 aligned"
                existing_review = db.get_dissonance_review(indicator["id"], row["id"])

                with st.expander(
                    f"{flag}  (semantic: {row['semantic_score']:.3f}, lexical: {row['lexical_score']:.3f}) "
                    f"— {row['feedback_text'][:60]}..."
                ):
                    st.write(row["feedback_text"])
                    st.caption(f"Cosine similarity to indicator: {row['semantic_score']:.3f} (reference only)")
                    if existing_review:
                        st.info(f"Previously reviewed: {existing_review['status']} — {existing_review['human_note'] or ''}")

                    if cached:
                        verdict_icon = {"supports": "✅", "contradicts": "⚠️", "unrelated": "⬜"}.get(
                            cached["verdict"], "❓"
                        )
                        st.write(f"{verdict_icon} **{cached['verdict']}** — {cached['reasoning']}")
                        if cached["verdict"] == "contradicts" and row["semantic_score"] >= threshold:
                            st.caption(
                                "Cosine similarity alone would have missed this — it scored above the "
                                "reference threshold. The entailment check caught it instead."
                            )

                    if st.button("Recheck with LLM", key=f"recheck_{indicator['id']}_{row['id']}"):
                        with st.spinner("Rechecking..."):
                            result = agents.check_entailment(indicator["indicator_text"], row["feedback_text"])
                        st.session_state[f"dissonance_entail_{indicator['id']}_{row['id']}"] = result
                        st.rerun()

                    note = st.text_input("Reviewer note (optional)", key=f"note_{indicator['id']}_{row['id']}")
                    rc1, rc2, rc3 = st.columns(3)
                    verdict_str = cached["verdict"] if cached else None
                    reasoning_str = cached["reasoning"] if cached else None
                    if rc1.button("Confirm dissonance", key=f"confirm_{indicator['id']}_{row['id']}"):
                        db.upsert_dissonance_review(
                            indicator["id"], row["id"], row["semantic_score"], row["lexical_score"],
                            verdict_str, reasoning_str, "confirmed_dissonance", note
                        )
                        st.rerun()
                    if rc2.button("Dismiss as noise", key=f"dismiss_{indicator['id']}_{row['id']}"):
                        db.upsert_dissonance_review(
                            indicator["id"], row["id"], row["semantic_score"], row["lexical_score"],
                            verdict_str, reasoning_str, "dismissed_as_noise", note
                        )
                        st.rerun()
                    if rc3.button("Needs more info", key=f"more_{indicator['id']}_{row['id']}"):
                        db.upsert_dissonance_review(
                            indicator["id"], row["id"], row["semantic_score"], row["lexical_score"],
                            verdict_str, reasoning_str, "needs_more_info", note
                        )
                        st.rerun()

            st.markdown("**Review summary for this indicator**")
            reviews = db.get_dissonance_reviews_for_indicator(indicator["id"])
            if reviews:
                st.dataframe(
                    pd.DataFrame(reviews)[["feedback_id", "semantic_score", "lexical_score",
                                            "entailment_verdict", "status", "human_note", "reviewed_at"]],
                    width="stretch",
                )
            else:
                st.caption("No reviews recorded yet.")

        st.divider()
        st.markdown("### 5c. Free-text synthesis")
        st.caption("Ad-hoc question answering across all feedback, independent of any single indicator.")

        question = st.text_input("Ask a synthesis question (e.g. 'What challenges came up?')")
        if st.button("Retrieve and synthesize") and question.strip():
            with st.spinner("Retrieving relevant feedback..."):
                passages = agents.retrieve_relevant_feedback(question, feedback_rows)
                synthesis = agents.synthesize_beneficiary_feedback(question, passages)
            st.session_state.last_synthesis = synthesis
            st.write("**Retrieved passages (raw, unedited):**")
            for p in passages:
                st.markdown(f"> {p}")
            st.write("**Synthesis:**", synthesis["synthesis"])
            if synthesis.get("outlier_or_dissenting_view"):
                st.warning(f"Preserved outlier view: {synthesis['outlier_or_dissenting_view']}")

# ---------------- Stage 6 ----------------
with tabs[5]:
    st.subheader("Stage 6 — Impact report agent")
    if not pid:
        st.warning("Complete stages 1-5 first.")
    else:
        approved = [i for i in db.get_indicators(pid) if i["status"] in ("approved", "edited")]
        if not approved:
            st.warning("No approved indicators to report on.")
        elif st.button("Generate impact report"):
            reports = db.get_field_reports(pid)
            sections = []
            with st.spinner("Generating bilateral assessment per indicator..."):
                for ind in approved:
                    evidence = []
                    for r in reports:
                        extracted = json.loads(r["extracted_json"])
                        for m in extracted.get("indicator_matches", []):
                            if m.get("indicator_text") == ind["indicator_text"] and m.get("evidence_quote"):
                                evidence.append(m)
                    synthesis_text = None
                    if "last_synthesis" in st.session_state:
                        synthesis_text = st.session_state.last_synthesis.get("synthesis")
                    section = agents.generate_impact_report_section(
                        ind["indicator_text"], evidence, synthesis_text
                    )
                    sections.append(section)
            report_json = {"sections": sections}
            db.insert_impact_report(pid, report_json)
            st.rerun()

        latest = db.get_latest_impact_report(pid)
        if latest:
            report_json = json.loads(latest["report_json"])
            for s in report_json["sections"]:
                st.markdown(f"### {s['indicator_text']}")
                st.write(f"Status: **{s['status']}**")
                st.write("Why on track:", ", ".join(s["why_high"]))
                st.write("Limiting factor:", ", ".join(s["why_low"]))
                if s.get("human_review_flag"):
                    st.warning(f"Flagged for human review: {s['human_review_flag']}")
            df = pd.DataFrame(report_json["sections"])
            st.download_button(
                "Download report as CSV", df.to_csv(index=False), file_name="impact_report.csv"
            )