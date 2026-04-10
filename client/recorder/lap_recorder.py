from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from poller.shared_memory import SharedMemoryReader
from poller.structs import ACCStatus, SPageFileStatic
from recorder.summarizer import summarize_lap
from store.database import init_db, insert_frame, mark_lap_summary

__all__ = ["RecorderThread"]


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "acc_coach.db"


def _wstring_to_str(value: Any) -> str:
    text = str(value)
    return text.split("\x00", 1)[0].strip()


def _json_compatible(value: Any) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return {key: _json_compatible(item) for key, item in value.model_dump().items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_compatible(item) for key, item in value.items()}
    return value


class RecorderThread(threading.Thread):
    """Consume poller queues, persist frames, and close laps on boundary events."""

    def __init__(
        self,
        physics_queue: queue.Queue[dict[str, object]],
        graphics_queue: queue.Queue[dict[str, object]],
        db_path: Path | None = None,
        idle_sleep_s: float = 0.02,
    ) -> None:
        super().__init__(daemon=True, name="RecorderThread")
        self._physics_queue = physics_queue
        self._graphics_queue = graphics_queue
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._idle_sleep_s = idle_sleep_s
        self._stop_event = threading.Event()
        self._reader = SharedMemoryReader()

        init_db(self._db_path)

        self.current_session_id: str | None = None
        self.current_lap: int | None = None
        self.last_completed_laps: int | None = None
        self.session_start_time: float | None = None

        self._session_started_at: datetime | None = None
        self._session_is_live = False
        self._session_needs_reset = True
        self._latest_status: int | None = None
        self._latest_penalty: int | None = None
        self._latest_session_time_left: float | None = None
        self._latest_current_sector_index: int | None = None
        self._latest_last_sector_time: int | None = None
        self._latest_track_grip_status: int | None = None
        self._latest_rain_intensity: int | None = None
        self._circuit: str = ""
        self._car_model: str = ""
        self._sector_count: int = 3
        self._recording_enabled: bool = False
        self._current_lap_frames: list[dict[str, object]] = []

    def stop(self) -> None:
        self._stop_event.set()

    def start_recording(self) -> None:
        self._recording_enabled = True

    def stop_recording(self) -> None:
        self._recording_enabled = False

    def run(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            while not self._stop_event.is_set():
                did_work = False
                did_work = self._drain_physics_queue(conn) or did_work
                did_work = self._drain_graphics_queue(conn) or did_work
                if not did_work:
                    self._stop_event.wait(self._idle_sleep_s)

            self._finalize_current_lap(conn, reason="stop")
        finally:
            conn.close()

    def _drain_graphics_queue(self, conn: sqlite3.Connection) -> bool:
        did_work = False
        while True:
            try:
                frame = self._graphics_queue.get_nowait()
            except queue.Empty:
                return did_work

            did_work = True
            try:
                self._handle_graphics_frame(conn, frame)
            except Exception:
                continue

    def _drain_physics_queue(self, conn: sqlite3.Connection) -> bool:
        did_work = False
        while True:
            try:
                frame = self._physics_queue.get_nowait()
            except queue.Empty:
                return did_work

            did_work = True
            try:
                self._handle_physics_frame(conn, frame)
            except Exception:
                continue

    def _handle_graphics_frame(self, conn: sqlite3.Connection, frame: dict[str, object]) -> None:
        status = int(frame.get("status", -1))
        completed_laps = int(frame.get("completed_laps", 0))

        self._latest_status = status
        self._latest_penalty = self._coerce_int(frame.get("penalty"))
        self._latest_session_time_left = self._coerce_float(frame.get("session_time_left"))
        self._latest_current_sector_index = self._coerce_int(frame.get("current_sector_index"))
        self._latest_last_sector_time = self._coerce_int(frame.get("last_sector_time"))
        self._latest_track_grip_status = self._coerce_int(frame.get("track_grip_status"))
        self._latest_rain_intensity = self._coerce_int(frame.get("rain_intensity"))

        # Treat ACC_LIVE and ACC_PAUSE as live - don't finalize laps on pause
        is_live = status in (ACCStatus.ACC_LIVE, ACCStatus.ACC_PAUSE)
        if not is_live:
            self._session_is_live = False
            self._session_needs_reset = True
            self.last_completed_laps = completed_laps
            return

        if self._session_needs_reset or self.current_session_id is None:
            if self.current_session_id is not None and self._current_lap_frames:
                self._finalize_current_lap(conn, reason="session_restart")
            self._begin_session(completed_laps)
            self._session_needs_reset = False
            self._session_is_live = True
            return

        if self.last_completed_laps is not None and completed_laps > self.last_completed_laps:
            self._finalize_current_lap(conn, reason="lap_boundary")
            self.current_lap = completed_laps + 1
            self._current_lap_frames = []

        self.last_completed_laps = completed_laps
        self._session_is_live = True

    def _handle_physics_frame(self, conn: sqlite3.Connection, frame: dict[str, object]) -> None:
        # Accept physics frames during LIVE and PAUSED states
        if self._latest_status not in (ACCStatus.ACC_LIVE, ACCStatus.ACC_PAUSE):
            return

        if self.current_session_id is None or self.current_lap is None or self.session_start_time is None:
            baseline_completed_laps = self.last_completed_laps if self.last_completed_laps is not None else 0
            self._begin_session(baseline_completed_laps)

        timestamp_ms = self._elapsed_ms()
        row = self._build_frame_payload(frame, timestamp_ms)
        self._current_lap_frames.append(row)
        insert_frame(
            conn,
            session_id=self.current_session_id or "",
            lap_number=self.current_lap or 1,
            packet_id=int(frame.get("packet_id", 0)),
            timestamp_ms=timestamp_ms,
            fields=row,
        )

    def _begin_session(self, completed_laps: int) -> None:
        self.current_session_id = uuid4().hex
        self.current_lap = max(1, completed_laps + 1)
        self.last_completed_laps = completed_laps
        self.session_start_time = time.monotonic()
        self._session_started_at = datetime.now(timezone.utc)
        self._session_is_live = True
        self._session_needs_reset = False
        self._current_lap_frames = []
        self._read_static_metadata()

    def _read_static_metadata(self) -> None:
        static = self._reader.read("acpmf_static", SPageFileStatic)
        if static is None:
            self._circuit = ""
            self._car_model = ""
            self._sector_count = 3
            return

        self._circuit = _wstring_to_str(getattr(static, "track", ""))
        self._car_model = _wstring_to_str(getattr(static, "carModel", ""))
        self._sector_count = self._coerce_sector_count(getattr(static, "sectorCount", None))

    def _build_frame_payload(self, frame: dict[str, object], timestamp_ms: int) -> dict[str, object]:
        payload = dict(frame)
        payload["timestamp_ms"] = timestamp_ms
        payload["session_id"] = self.current_session_id
        payload["lap_number"] = self.current_lap
        payload["status"] = self._latest_status
        payload["completed_laps"] = self.last_completed_laps
        payload["penalty"] = self._latest_penalty
        payload["session_time_left"] = self._latest_session_time_left
        payload["current_sector_index"] = self._latest_current_sector_index
        payload["last_sector_time"] = self._latest_last_sector_time
        payload["track_grip_status"] = self._latest_track_grip_status
        payload["rain_intensity"] = self._latest_rain_intensity
        payload["sector_count"] = self._sector_count
        return payload

    def _finalize_current_lap(self, conn: sqlite3.Connection, reason: str) -> None:
        if self.current_session_id is None or self.current_lap is None:
            self._current_lap_frames = []
            return

        frames = self._current_lap_frames
        if not frames:
            return
        if not self._recording_enabled:
            self._current_lap_frames = []
            return

        lap_time_ms = self._lap_duration_ms(frames)
        is_valid = not any(self._frame_penalized(frame) for frame in frames)
        summary = summarize_lap(
            frames,
            self.current_session_id,
            self.current_lap,
            self._circuit or "",
            self._car_model or "",
            self._sector_count,
        )
        summary_json = json.dumps(_json_compatible(summary), ensure_ascii=False, separators=(",", ":"))
        mark_lap_summary(
            conn,
            session_id=self.current_session_id,
            lap_number=self.current_lap,
            lap_time_ms=lap_time_ms,
            is_valid=is_valid,
            circuit=self._circuit or None,
            car_model=self._car_model or None,
            summary_json=summary_json,
        )
        self._current_lap_frames = []

    def _lap_duration_ms(self, frames: list[dict[str, object]]) -> int:
        first_timestamp = self._coerce_int(frames[0].get("timestamp_ms")) if frames else 0
        last_timestamp = self._coerce_int(frames[-1].get("timestamp_ms")) if frames else 0
        return max(0, last_timestamp - first_timestamp)

    @staticmethod
    def _frame_penalized(frame: dict[str, object]) -> bool:
        penalty = frame.get("penalty")
        if penalty is None:
            return False
        try:
            return int(penalty) != 0
        except (TypeError, ValueError):
            return bool(penalty)

    def _elapsed_ms(self) -> int:
        if self.session_start_time is None:
            self.session_start_time = time.monotonic()
        return max(0, int((time.monotonic() - self.session_start_time) * 1000))

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_sector_count(value: object) -> int:
        try:
            sector_count = int(value)
        except (TypeError, ValueError):
            return 3
        return sector_count if sector_count > 0 else 3


if __name__ == "__main__":
    import queue as _queue

    physics_queue: _queue.Queue[dict[str, object]] = _queue.Queue()
    graphics_queue: _queue.Queue[dict[str, object]] = _queue.Queue()
    recorder = RecorderThread(physics_queue, graphics_queue)
    recorder.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        recorder.stop()
        recorder.join(timeout=2.0)
