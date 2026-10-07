"""SQLite persistence for players, rooms, chat messages and dice rolls."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DICE_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "dice.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_by  INTEGER NOT NULL REFERENCES players(id),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id     INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    joined_at   TEXT NOT NULL,
    PRIMARY KEY (room_id, player_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    player_id   INTEGER REFERENCES players(id),
    kind        TEXT NOT NULL,          -- 'chat' | 'system'
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Rolls are kept as history even after their room is deleted,
-- so room_id is nullable and the room name is denormalized.
CREATE TABLE IF NOT EXISTS rolls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
    room_name   TEXT NOT NULL,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    expression  TEXT NOT NULL,
    detail      TEXT NOT NULL,          -- JSON with every die rolled
    total       INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
CREATE INDEX IF NOT EXISTS idx_rolls_room ON rolls(room_id, id);
CREATE INDEX IF NOT EXISTS idx_rolls_player ON rolls(player_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # No WebSocket connections survive a restart, so any room left in the
        # database is stale and must be removed.
        conn.execute("DELETE FROM rooms")


# ---------- players ----------

def upsert_player(username: str) -> dict:
    ts = now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO players (username, created_at, last_seen) VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (username, ts, ts),
        )
        row = conn.execute("SELECT * FROM players WHERE username = ?", (username,)).fetchone()
        return dict(row)


# ---------- rooms ----------

def list_rooms() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.name, r.created_at, p.username AS created_by,
                   COUNT(m.player_id) AS player_count
            FROM rooms r
            JOIN players p ON p.id = r.created_by
            LEFT JOIN room_members m ON m.room_id = r.id
            GROUP BY r.id
            ORDER BY r.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_room(name: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM rooms WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def create_room(name: str, player_id: int) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO rooms (name, created_by, created_at) VALUES (?, ?, ?)",
            (name, player_id, now()),
        )
        row = conn.execute("SELECT * FROM rooms WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def delete_room(room_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))


def add_member(room_id: int, player_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO room_members (room_id, player_id, joined_at) VALUES (?, ?, ?)",
            (room_id, player_id, now()),
        )


def remove_member(room_id: int, player_id: int) -> int:
    """Remove a member and return how many members remain in the room."""
    with connect() as conn:
        conn.execute(
            "DELETE FROM room_members WHERE room_id = ? AND player_id = ?",
            (room_id, player_id),
        )
        conn.execute("UPDATE players SET last_seen = ? WHERE id = ?", (now(), player_id))
        return conn.execute(
            "SELECT COUNT(*) FROM room_members WHERE room_id = ?", (room_id,)
        ).fetchone()[0]


def list_members(room_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.username, m.joined_at
            FROM room_members m JOIN players p ON p.id = m.player_id
            WHERE m.room_id = ?
            ORDER BY m.joined_at, p.username
            """,
            (room_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- messages & rolls ----------

def save_message(room_id: int, player_id: int | None, kind: str, text: str) -> dict:
    ts = now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (room_id, player_id, kind, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (room_id, player_id, kind, text, ts),
        )
        return {"id": cur.lastrowid, "kind": kind, "text": text, "created_at": ts}


def save_roll(room: dict, player_id: int, expression: str, detail: dict, total: int) -> dict:
    ts = now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO rolls (room_id, room_name, player_id, expression, detail, total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (room["id"], room["name"], player_id, expression, json.dumps(detail), total, ts),
        )
        return {"id": cur.lastrowid, "created_at": ts}


def room_history(room_id: int, limit: int = 100) -> list[dict]:
    """Return the latest chat messages and rolls of a room, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT 'chat' AS type, m.kind AS kind, m.text AS text, NULL AS detail,
                       NULL AS total, m.created_at AS created_at, p.username AS username
                FROM messages m LEFT JOIN players p ON p.id = m.player_id
                WHERE m.room_id = ?
                UNION ALL
                SELECT 'roll' AS type, NULL, r.expression, r.detail, r.total,
                       r.created_at, p.username
                FROM rolls r JOIN players p ON p.id = r.player_id
                WHERE r.room_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (room_id, room_id, limit),
        ).fetchall()

    history = []
    for row in rows:
        if row["type"] == "roll":
            history.append({
                "type": "roll",
                "username": row["username"],
                "result": json.loads(row["detail"]),
                "created_at": row["created_at"],
            })
        else:
            history.append({
                "type": row["kind"],
                "username": row["username"],
                "text": row["text"],
                "created_at": row["created_at"],
            })
    return history


def player_rolls(username: str, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT r.room_name, r.expression, r.total, r.detail, r.created_at
            FROM rolls r JOIN players p ON p.id = r.player_id
            WHERE p.username = ?
            ORDER BY r.id DESC LIMIT ?
            """,
            (username, limit),
        ).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]
