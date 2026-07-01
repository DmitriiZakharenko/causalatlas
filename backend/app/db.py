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
    autonomy_level  TEXT NOT NULL,
    status          TEXT NOT NULL,       -- pending|running|paused|completed|failed
    current_agent   TEXT,
    error           TEXT,
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
"""


async def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def create_run(
    run_id: str,
    disease: str,
    gene: str | None,
    autonomy_level: str,
    db_path: Path | None = None,
) -> None:
    now = time.time()
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        await db.execute(
            "INSERT INTO runs (run_id, disease, gene, autonomy_level, status, "
            "current_agent, error, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', "
            "NULL, NULL, ?, ?)",
            (run_id, disease, gene, autonomy_level, now, now),
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
) -> int:
    """Append an event and return its sequence number (per-run, starting at 0)."""
    async with aiosqlite.connect(db_path or DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM run_events WHERE run_id = ?", (run_id,)
        )
        (seq,) = await cursor.fetchone()
        await db.execute(
            "INSERT INTO run_events (run_id, seq, event_type, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, event_type, json.dumps(payload), time.time()),
        )
        await db.commit()
        return seq


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
