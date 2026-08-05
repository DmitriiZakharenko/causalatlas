"""
Phase 2: SQLite run-metadata store (per Phase 0's "SQLite (or DuckDB) for run
metadata + eval scores -- do not use a heavyweight DB" constraint).

Two tables:
- `runs`: one row per pipeline run, current status, autonomy level, timestamps.
- `run_events`: append-only log of every SSE event ever emitted for a run, so
  a UI reconnecting mid-run (or after a page reload) can replay history instead
  of losing the live progress view. This is also the durable source of truth
  the eval flywheel (Phase 4) and the audit trail (Phase 3's human-correction
  logging) both read from.

No ORM (SQLAlchemy is in requirements.txt for later phases if needed, but a
prototype with two small tables does not need it) -- plain `aiosqlite` keeps
this auditable in one file.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import aiosqlite

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "loopfinder.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    disease         TEXT NOT NULL,
    gene            TEXT,
    target_schema_version TEXT,
    target_json     TEXT,
    autonomy_level  TEXT NOT NULL,
    status          TEXT NOT NULL,       -- pending|running|paused|completed|failed
    current_agent   TEXT,
    error           TEXT,
    session_id      TEXT,                -- Phase 3: claude CLI session id, set at
                                          -- creation so a "paused" run can be resumed
                                          -- later via `claude --resume <session_id>`
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,           -- JSON-encoded dict
    created_at  REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id, seq);

CREATE TABLE IF NOT EXISTS human_interventions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    decision    TEXT NOT NULL,           -- approve|reject|edit
    note        TEXT,
    created_at  REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS eval_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type    TEXT NOT NULL,       -- 'historical_backfill' | 'live_judge'
    session_id      TEXT NOT NULL,       -- e.g. 'asthma_001', or a live pipeline run_id
    hypothesis_id   TEXT,                -- NULL for a graph/run-level (not per-hypothesis) score
    original_label  TEXT,                -- the pipeline's own classification/verdict at the time
    ground_truth    TEXT,                -- later-established real classification, if known
    outcome         TEXT NOT NULL,       -- see eval.py's Outcome constants for the fixed vocabulary
    reasoning       TEXT,
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_scores_session ON eval_scores(session_id);
"""


# `CREATE TABLE IF NOT EXISTS` is a no-op for a table that already exists
# with an OLDER shape -- discovered live when the first real full pipeline
# run failed instantly with "table runs has no column named session_id",
# because the on-disk data/loopfinder.db predated Phase 3 adding that column
# and nothing had ever migrated it. This is the minimal fix: on every
# startup, add any columns the current schema expects but the on-disk table
# doesn't have yet. Additive-only (never drops/renames), same non-destructive
# spirit as Agent 6's graph-merge constraint.
_COLUMN_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "runs": [
        ("session_id", "TEXT"),
        ("target_schema_version", "TEXT"),
        ("target_json", "TEXT"),
    ],
}


async def _apply_column_migrations(db: aiosqlite.Connection) -> None:
    for table, columns in _COLUMN_MIGRATIONS.items():
        cursor = await db.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        for name, col_type in columns:
            if name not in existing:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")


async def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(_SCHEMA)
        await _apply_column_migrations(db)
        await db.commit()


async def create_run(
    run_id: str,
    disease: str,
    gene: str | None,
    autonomy_level: str,
    session_id: str | None = None,
    target_schema_version: str | None = None,
    target_json: str | None = None,
    db_path: Path | None = None,
) -> None:
    now = time.time()
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        await db.execute(
            "INSERT INTO runs (run_id, disease, gene, target_schema_version, target_json, autonomy_level, status, "
            "current_agent, error, session_id, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?, ?)",
            (run_id, disease, gene, target_schema_version, target_json, autonomy_level, session_id, now, now),
        )
        await db.commit()


async def update_run_status(
    run_id: str,
    status: str,
    *,
    current_agent: str | None = None,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        # NULLIF(?, '') matters: a duplicate/late terminal event with an empty
        # error string (e.g. claude_cli's synthetic `orchestrator_failed`
        # wrapper firing after a "result" event already reported the real
        # failure reason, with nothing new in stderr) must NOT clobber an
        # already-recorded real error message. Discovered live (Phase 2
        # dev-loop run hit a real Claude subscription rate limit): the run's
        # `error` column came back as "" even though the SSE stream showed
        # the real "You've hit your limit..." reason a moment earlier.
        await db.execute(
            "UPDATE runs SET status = ?, current_agent = COALESCE(?, current_agent), "
            "error = COALESCE(NULLIF(?, ''), error), updated_at = ? WHERE run_id = ?",
            (status, current_agent, error, time.time(), run_id),
        )
        await db.commit()


async def get_run(run_id: str, db_path: Path | None = None) -> dict | None:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_runs(db_path: Path | None = None) -> list[dict]:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM runs ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def append_event(
    run_id: str,
    event_type: str,
    payload: dict,
    db_path: Path | None = None,
) -> tuple[int, float]:
    """Append an event and return its (sequence number, created_at)."""
    created_at = time.time()
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM run_events WHERE run_id = ?", (run_id,)
        )
        (seq,) = await cursor.fetchone()
        await db.execute(
            "INSERT INTO run_events (run_id, seq, event_type, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, event_type, json.dumps(payload), created_at),
        )
        await db.commit()
        return seq, created_at


async def get_events_since(
    run_id: str, after_seq: int = -1, db_path: Path | None = None
) -> list[dict]:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM run_events WHERE run_id = ? AND seq > ? ORDER BY seq ASC",
            (run_id, after_seq),
        )
        rows = await cursor.fetchall()
        return [
            {
                "seq": r["seq"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


async def record_human_intervention(
    run_id: str,
    agent_name: str,
    decision: str,
    note: str | None,
    db_path: Path | None = None,
) -> None:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        await db.execute(
            "INSERT INTO human_interventions (run_id, agent_name, decision, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, agent_name, decision, note, time.time()),
        )
        await db.commit()


async def get_human_interventions(run_id: str, db_path: Path | None = None) -> list[dict]:
    """Phase 3 audit trail: every human approve/reject/edit decision recorded
    against a run, oldest first -- this is the record a supervised/autocomplete
    run's pauses actually got a real human sign-off, not just a UI checkbox."""
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM human_interventions WHERE run_id = ? ORDER BY created_at ASC",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def record_eval_score(
    subject_type: str,
    session_id: str,
    outcome: str,
    *,
    hypothesis_id: str | None = None,
    original_label: str | None = None,
    ground_truth: str | None = None,
    reasoning: str | None = None,
    db_path: Path | None = None,
) -> None:
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        await db.execute(
            "INSERT INTO eval_scores (subject_type, session_id, hypothesis_id, original_label, "
            "ground_truth, outcome, reasoning, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                subject_type,
                session_id,
                hypothesis_id,
                original_label,
                ground_truth,
                outcome,
                reasoning,
                time.time(),
            ),
        )
        await db.commit()


async def clear_eval_scores(subject_type: str, db_path: Path | None = None) -> None:
    """Backfill is idempotent: re-running it must replace, not accumulate,
    the previous `historical_backfill` rows (it always recomputes the full
    set from the same real files) -- without this, re-running the endpoint
    twice would silently double-count every dashboard metric."""
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        await db.execute("DELETE FROM eval_scores WHERE subject_type = ?", (subject_type,))
        await db.commit()


async def list_eval_scores(
    *,
    subject_type: str | None = None,
    session_id: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    query = "SELECT * FROM eval_scores"
    clauses = []
    params: list[str] = []
    if subject_type is not None:
        clauses.append("subject_type = ?")
        params.append(subject_type)
    if session_id is not None:
        clauses.append("session_id = ?")
        params.append(session_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at ASC"
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
