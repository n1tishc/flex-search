from __future__ import annotations

import aiosqlite
from pathlib import Path

from app.config import settings

_db: aiosqlite.Connection | None = None
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    global _db
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    schema_sql = _SCHEMA_PATH.read_text()
    await _db.executescript(schema_sql)
    await _db.commit()


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
