"""
SQLite storage layer for the hybrid human-AI M&E pipeline demo.
One file, one folder, no server — the .db file is created next to this
script the first time init_db() runs. Safe to commit .gitignore'd out
(see .gitignore) since it's regenerated on first run / re-seeded on demand.
"""

import sqlite3
import json
import datetime

DB_PATH = "me_pipeline.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text TEXT,
        extracted_json TEXT,
        me_model_choice TEXT,
        me_model_rationale TEXT,
        created_at TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proposal_id INTEGER,
        indicator_text TEXT,
        objective_link TEXT,
        status TEXT DEFAULT 'draft',   -- draft | approved | rejected | edited
        created_at TEXT,
        FOREIGN KEY (proposal_id) REFERENCES proposals(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS field_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proposal_id INTEGER,
        report_text TEXT,
        extracted_json TEXT,
        anomaly_flag INTEGER DEFAULT 0,
        anomaly_reason TEXT,
        created_at TEXT,
        FOREIGN KEY (proposal_id) REFERENCES proposals(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS beneficiary_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proposal_id INTEGER,
        feedback_text TEXT,
        embedding TEXT,   -- JSON-encoded float list
        created_at TEXT,
        FOREIGN KEY (proposal_id) REFERENCES proposals(id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS impact_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proposal_id INTEGER,
        report_json TEXT,
        created_at TEXT,
        FOREIGN KEY (proposal_id) REFERENCES proposals(id)
    )""")

    conn.commit()
    conn.close()


def _now():
    return datetime.datetime.utcnow().isoformat()


# ---------- proposals ----------

def insert_proposal(raw_text, extracted_json):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO proposals (raw_text, extracted_json, created_at) VALUES (?, ?, ?)",
        (raw_text, json.dumps(extracted_json), _now()),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def set_me_model_choice(proposal_id, model_choice, rationale):
    conn = get_connection()
    conn.execute(
        "UPDATE proposals SET me_model_choice = ?, me_model_rationale = ? WHERE id = ?",
        (model_choice, rationale, proposal_id),
    )
    conn.commit()
    conn.close()


def get_proposal(proposal_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_proposals():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM proposals ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- indicators ----------

def insert_indicators(proposal_id, indicator_list):
    """indicator_list: list of dicts with 'indicator_text' and 'objective_link'."""
    conn = get_connection()
    cur = conn.cursor()
    for ind in indicator_list:
        cur.execute(
            "INSERT INTO indicators (proposal_id, indicator_text, objective_link, status, created_at) "
            "VALUES (?, ?, ?, 'draft', ?)",
            (proposal_id, ind["indicator_text"], ind.get("objective_link", ""), _now()),
        )
    conn.commit()
    conn.close()


def update_indicator_status(indicator_id, status, new_text=None):
    conn = get_connection()
    if new_text is not None:
        conn.execute(
            "UPDATE indicators SET status = ?, indicator_text = ? WHERE id = ?",
            (status, new_text, indicator_id),
        )
    else:
        conn.execute("UPDATE indicators SET status = ? WHERE id = ?", (status, indicator_id))
    conn.commit()
    conn.close()


def get_indicators(proposal_id, status=None):
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM indicators WHERE proposal_id = ? AND status = ? ORDER BY id",
            (proposal_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM indicators WHERE proposal_id = ? ORDER BY id", (proposal_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- field reports (continuous monitoring) ----------

def insert_field_report(proposal_id, report_text, extracted_json, anomaly_flag, anomaly_reason):
    conn = get_connection()
    conn.execute(
        "INSERT INTO field_reports (proposal_id, report_text, extracted_json, anomaly_flag, "
        "anomaly_reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (proposal_id, report_text, json.dumps(extracted_json), int(anomaly_flag), anomaly_reason, _now()),
    )
    conn.commit()
    conn.close()


def get_field_reports(proposal_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM field_reports WHERE proposal_id = ? ORDER BY id DESC", (proposal_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- beneficiary feedback ----------

def insert_feedback(proposal_id, feedback_text, embedding):
    conn = get_connection()
    conn.execute(
        "INSERT INTO beneficiary_feedback (proposal_id, feedback_text, embedding, created_at) "
        "VALUES (?, ?, ?, ?)",
        (proposal_id, feedback_text, json.dumps(embedding), _now()),
    )
    conn.commit()
    conn.close()


def get_feedback(proposal_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM beneficiary_feedback WHERE proposal_id = ?", (proposal_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- impact reports ----------

def insert_impact_report(proposal_id, report_json):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO impact_reports (proposal_id, report_json, created_at) VALUES (?, ?, ?)",
        (proposal_id, json.dumps(report_json), _now()),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_latest_impact_report(proposal_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM impact_reports WHERE proposal_id = ? ORDER BY id DESC LIMIT 1",
        (proposal_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
