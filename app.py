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
            if st.button("Load demo field reports"):
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
        if st.button("Load demo beneficiary feedback"):
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