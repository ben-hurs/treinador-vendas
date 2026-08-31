"""
Camada de acesso ao banco de dados.
Local: SQLite (arquivo único, zero configuração).
Quando escalar: trocar só esse arquivo para usar Postgres (psycopg2/SQLAlchemy) —
o resto do app (app.py) não precisa mudar, porque só chama essas funções.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "sales_trainer.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection():
    # timeout maior + modo WAL: com várias pessoas usando o app ao mesmo tempo,
    # o SQLite passa a permitir leituras e escritas concorrentes sem estourar
    # "database is locked" (o padrão do SQLite é bem mais restritivo nisso).
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def seed_scenarios(scenarios):
    conn = get_connection()
    for s in scenarios:
        conn.execute(
            """INSERT OR IGNORE INTO scenarios (id, name, difficulty, pitch, system_prompt)
               VALUES (?, ?, ?, ?, ?)""",
            (s["id"], s["name"], s["difficulty"], s["pitch"], s["system_prompt"]),
        )
    conn.commit()
    conn.close()


def list_scenarios():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM scenarios ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_session(scenario_id: str) -> int:
    conn = get_connection()
    cur = conn.execute("INSERT INTO sessions (scenario_id) VALUES (?)", (scenario_id,))
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def add_message(session_id: int, role: str, content: str, mood: int = None, trust: int = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, mood, trust) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, mood, trust),
    )
    conn.commit()
    conn.close()


def get_messages(session_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def end_session(session_id: int, final_mood: int, final_trust: int, overall_score: int):
    conn = get_connection()
    conn.execute(
        """UPDATE sessions
           SET ended_at = CURRENT_TIMESTAMP, final_mood = ?, final_trust = ?, overall_score = ?
           WHERE id = ?""",
        (final_mood, final_trust, overall_score, session_id),
    )
    conn.commit()
    conn.close()


def save_feedback(session_id, summary, strengths, improvements, best_moment, missed_moment):
    conn = get_connection()
    conn.execute(
        """INSERT INTO feedback (session_id, summary, strengths, improvements, best_moment, missed_moment)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            summary,
            json.dumps(strengths, ensure_ascii=False),
            json.dumps(improvements, ensure_ascii=False),
            best_moment,
            missed_moment,
        ),
    )
    conn.commit()
    conn.close()


def get_history():
    """Sessões concluídas, mais recentes primeiro — útil pra acompanhar evolução."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.id, sc.name AS scenario, s.started_at, s.overall_score,
                  s.final_mood, s.final_trust
           FROM sessions s
           JOIN scenarios sc ON s.scenario_id = sc.id
           WHERE s.ended_at IS NOT NULL
           ORDER BY s.started_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
