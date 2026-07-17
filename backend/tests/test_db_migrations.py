"""
Regression test for a real bug found on the first live full pipeline run:
the on-disk data/loopfinder.db predated Phase 3's `session_id` column, and
`CREATE TABLE IF NOT EXISTS` silently does nothing for a table that already
exists with an older shape -- `create_run()` failed with
"table runs has no column named session_id" the instant a real run was
launched. `init_db()` must heal an old on-disk table in place.
"""
from __future__ import annotations

import aiosqlite
import pytest

from app import db as db_mod


@pytest.mark.asyncio
async def test_init_db_adds_session_id_to_a_pre_phase3_runs_table(tmp_path):
    db_path = tmp_path / "old.db"
    # Recreate the exact pre-Phase-3 schema (no session_id column) that the
    # real data/loopfinder.db had on disk.
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                disease TEXT NOT NULL,
                gene TEXT,
                autonomy_level TEXT NOT NULL,
                status TEXT NOT NULL,
                current_agent TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        await conn.commit()

    await db_mod.init_db(db_path)

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA table_info(runs)")
        columns = {row[1] for row in await cursor.fetchall()}
    assert "session_id" in columns

    # And create_run must actually work against the healed table now.
    await db_mod.create_run("run_1", "asthma", None, "let_it_rip", session_id="sess_1", db_path=db_path)
    row = await db_mod.get_run("run_1", db_path=db_path)
    assert row["session_id"] == "sess_1"


@pytest.mark.asyncio
async def test_init_db_is_idempotent_on_an_already_migrated_table(tmp_path):
    db_path = tmp_path / "fresh.db"
    await db_mod.init_db(db_path)
    await db_mod.init_db(db_path)  # must not raise "duplicate column"
    await db_mod.create_run("run_2", "ibd", "IL23A", "supervised", session_id="sess_2", db_path=db_path)
    row = await db_mod.get_run("run_2", db_path=db_path)
    assert row["session_id"] == "sess_2"
