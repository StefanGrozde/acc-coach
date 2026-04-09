from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


Connection = sqlite3.Connection


FRAME_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "distance_m": ("distance_m", "distance_traveled"),
    "speed_kmh": ("speed_kmh", "speedKmh"),
    "brake": ("brake",),
    "throttle": ("throttle",),
    "gear": ("gear",),
    "rpms": ("rpms",),
    "steer_angle": ("steer_angle", "steer", "steerAngle"),
    "abs_active": ("abs_active", "abs"),
    "tc_active": ("tc_active", "tc"),
}


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS frames (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    lap_number  INTEGER NOT NULL,
    packet_id   INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,

    distance_m      REAL,
    speed_kmh       REAL,
    brake           REAL,
    throttle        REAL,
    gear            INTEGER,
    rpms            INTEGER,
    steer_angle     REAL,
    abs_active      REAL,
    tc_active       REAL,

    raw_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_frames_session_lap ON frames(session_id, lap_number);

CREATE TABLE IF NOT EXISTS laps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    lap_number  INTEGER NOT NULL,
    lap_time_ms INTEGER,
    is_valid    INTEGER,
    circuit     TEXT,
    car_model   TEXT,
    recorded_at TEXT,
    summary_json TEXT,
    uploaded    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reference_laps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    circuit     TEXT NOT NULL,
    car_model   TEXT NOT NULL,
    lap_time_ms INTEGER,
    source      TEXT,
    summary_json TEXT,
    added_at    TEXT
);
"""


def init_db(db_path: Path) -> None:
    """Create the client SQLite schema if it does not already exist."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()


def insert_frame(
    conn: Connection,
    session_id: str,
    lap_number: int,
    packet_id: int,
    timestamp_ms: int,
    fields: dict[str, Any],
) -> None:
    """Insert one raw frame row and preserve the original payload as JSON."""

    payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"), default=str)
    values = {
        "session_id": session_id,
        "lap_number": lap_number,
        "packet_id": packet_id,
        "timestamp_ms": timestamp_ms,
        "distance_m": _first_present(fields, FRAME_FIELD_ALIASES["distance_m"]),
        "speed_kmh": _first_present(fields, FRAME_FIELD_ALIASES["speed_kmh"]),
        "brake": _first_present(fields, FRAME_FIELD_ALIASES["brake"]),
        "throttle": _first_present(fields, FRAME_FIELD_ALIASES["throttle"]),
        "gear": _first_present(fields, FRAME_FIELD_ALIASES["gear"]),
        "rpms": _first_present(fields, FRAME_FIELD_ALIASES["rpms"]),
        "steer_angle": _first_present(fields, FRAME_FIELD_ALIASES["steer_angle"]),
        "abs_active": _first_present(fields, FRAME_FIELD_ALIASES["abs_active"]),
        "tc_active": _first_present(fields, FRAME_FIELD_ALIASES["tc_active"]),
        "raw_json": payload,
    }

    with conn:
        conn.execute(
            """
            INSERT INTO frames (
                session_id, lap_number, packet_id, timestamp_ms,
                distance_m, speed_kmh, brake, throttle, gear, rpms,
                steer_angle, abs_active, tc_active, raw_json
            ) VALUES (
                :session_id, :lap_number, :packet_id, :timestamp_ms,
                :distance_m, :speed_kmh, :brake, :throttle, :gear, :rpms,
                :steer_angle, :abs_active, :tc_active, :raw_json
            )
            """,
            values,
        )


def mark_lap_summary(
    conn: Connection,
    session_id: str,
    lap_number: int,
    lap_time_ms: int | None,
    is_valid: bool | int | None,
    circuit: str | None,
    car_model: str | None,
    summary_json: str,
) -> None:
    """Insert or update a lap summary while keeping uploaded reset to 0."""

    recorded_at = _utc_now_iso()
    is_valid_int = None if is_valid is None else int(bool(is_valid))

    with conn:
        cursor = conn.execute(
            """
            UPDATE laps
            SET lap_time_ms = ?,
                is_valid = ?,
                circuit = ?,
                car_model = ?,
                recorded_at = ?,
                summary_json = ?,
                uploaded = 0
            WHERE session_id = ? AND lap_number = ?
            """,
            (
                lap_time_ms,
                is_valid_int,
                circuit,
                car_model,
                recorded_at,
                summary_json,
                session_id,
                lap_number,
            ),
        )

        if cursor.rowcount == 0:
            conn.execute(
                """
                INSERT INTO laps (
                    session_id, lap_number, lap_time_ms, is_valid,
                    circuit, car_model, recorded_at, summary_json, uploaded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    lap_number,
                    lap_time_ms,
                    is_valid_int,
                    circuit,
                    car_model,
                    recorded_at,
                    summary_json,
                ),
            )


def _first_present(fields: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        if key in fields:
            return fields[key]
    return None


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    import tempfile

    temp_dir = Path(tempfile.gettempdir())
    db_path = temp_dir / "acc_coach_database_self_test.db"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        insert_frame(
            conn,
            session_id="session-1",
            lap_number=1,
            packet_id=123,
            timestamp_ms=456,
            fields={
                "distance_m": 12.5,
                "speed_kmh": 167.2,
                "brake": 0.1,
                "throttle": 0.8,
                "gear": 3,
                "rpms": 9200,
                "steer_angle": -0.05,
                "abs_active": 0.0,
                "tc_active": 0.0,
            },
        )
        mark_lap_summary(
            conn,
            session_id="session-1",
            lap_number=1,
            lap_time_ms=91234,
            is_valid=True,
            circuit="spa",
            car_model="mclaren_720s_gt3",
            summary_json='{"lap_number":1}',
        )
        frame_count = conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
        lap_row = conn.execute(
            "SELECT uploaded, lap_time_ms FROM laps WHERE session_id = ? AND lap_number = ?",
            ("session-1", 1),
        ).fetchone()
    print(f"self-check ok: frames={frame_count}, lap={lap_row}")
