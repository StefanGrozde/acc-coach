from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json as _json
import logging
from pathlib import Path
import sqlite3
import threading
import time
import tomllib
from typing import Any
import urllib.error
import urllib.request

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised only when the dependency is absent.
    class _FallbackResponse:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    class _FallbackHTTPX:
        class HTTPError(Exception):
            pass

        @staticmethod
        def post(
            url: str,
            json: Any | None = None,
            headers: dict[str, str] | None = None,
            timeout: float | None = None,
        ) -> _FallbackResponse:
            payload = _json.dumps(json).encode("utf-8")
            request_headers = {"Content-Type": "application/json"}
            if headers:
                request_headers.update(headers)

            request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    text = response.read().decode("utf-8", errors="replace")
                    return _FallbackResponse(int(response.getcode()), text)
            except urllib.error.HTTPError as exc:
                text = exc.read().decode("utf-8", errors="replace")
                return _FallbackResponse(int(exc.code), text)
            except urllib.error.URLError as exc:
                raise _FallbackHTTPX.HTTPError(str(exc)) from exc

    httpx = _FallbackHTTPX()

from client.store.database import init_db
from shared.models import LapSummary

__all__ = ["UploaderThread"]


logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"
DEFAULT_API_KEY = "your-secret-key-here"
DEFAULT_SESSION_TYPE = "UNKNOWN"
DEFAULT_SESSION_FIELD = "UNKNOWN"
DEFAULT_POLL_INTERVAL_S = 5.0
DEFAULT_REQUEST_TIMEOUT_S = 15.0


@dataclass(slots=True)
class _PendingLap:
    row_id: int
    session_id: str
    lap_number: int
    summary: LapSummary
    circuit: str
    car_model: str
    recorded_at: datetime


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "acc_coach.db"


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config.toml"


def _normalize_base_url(url: str) -> str:
    cleaned = url.strip()
    return cleaned.rstrip("/") if cleaned else DEFAULT_BACKEND_URL


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            try:
                return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _load_backend_config(config_path: Path) -> dict[str, Any]:
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {
            "url": DEFAULT_BACKEND_URL,
            "api_key": DEFAULT_API_KEY,
            "upload_enabled": True,
        }

    backend = data.get("backend", {}) if isinstance(data, dict) else {}
    if not isinstance(backend, dict):
        backend = {}

    return {
        "url": str(backend.get("url", DEFAULT_BACKEND_URL)),
        "api_key": str(backend.get("api_key", DEFAULT_API_KEY)),
        "upload_enabled": _coerce_bool(backend.get("upload_enabled", True)),
    }


def _load_lap_summary(summary_json: str) -> LapSummary:
    validator = getattr(LapSummary, "model_validate_json", None)
    if callable(validator):
        return validator(summary_json)

    data = _json.loads(summary_json)
    return LapSummary.model_validate(data)


def _dump_lap_summary(summary: LapSummary) -> dict[str, Any]:
    serializer = getattr(summary, "model_dump_json", None)
    if callable(serializer):
        return _json.loads(serializer())

    dump = getattr(summary, "model_dump", None)
    if callable(dump):
        try:
            payload = dump(mode="json")
        except TypeError:
            payload = dump()
        return _json_ready(payload)

    legacy_json = getattr(summary, "json", None)
    if callable(legacy_json):
        return _json.loads(legacy_json())

    raise TypeError("LapSummary does not support JSON serialization")


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]

    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            nested = dump(mode="json")
        except TypeError:
            nested = dump()
        return _json_ready(nested)

    legacy_dict = getattr(value, "dict", None)
    if callable(legacy_dict):
        return _json_ready(legacy_dict())

    return value


class UploaderThread(threading.Thread):
    def __init__(
        self,
        db_path: Path | None = None,
        config_path: Path | None = None,
        backend_url: str | None = None,
        api_key: str | None = None,
        upload_enabled: bool | None = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S,
    ) -> None:
        super().__init__(daemon=True, name="UploaderThread")
        self._stop_event = threading.Event()
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._config_path = Path(config_path) if config_path is not None else _default_config_path()
        config = _load_backend_config(self._config_path)

        self._backend_url = _normalize_base_url(backend_url or str(config["url"]))
        self._api_key = api_key if api_key is not None else str(config["api_key"])
        self._upload_enabled = _coerce_bool(config["upload_enabled"]) if upload_enabled is None else bool(upload_enabled)
        self._poll_interval_s = float(poll_interval_s)
        self._request_timeout_s = float(request_timeout_s)
        self._known_sessions: set[str] = set()

        init_db(self._db_path)

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if not self._upload_enabled:
            logger.info("UploaderThread disabled by configuration")
            return

        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            while not self._stop_event.is_set():
                try:
                    self._poll_once(conn)
                except Exception:
                    logger.exception("Uploader cycle failed")
                if self._stop_event.wait(self._poll_interval_s):
                    break
        finally:
            conn.close()

    def _poll_once(self, conn: sqlite3.Connection) -> int:
        pending = self._load_pending_laps(conn)
        if not pending:
            return 0

        uploaded_count = 0
        for session_id, laps in pending.items():
            if not self._ensure_session(laps[0]):
                continue

            for lap in laps:
                if self._upload_lap(conn, lap):
                    uploaded_count += 1

        return uploaded_count

    def _load_pending_laps(self, conn: sqlite3.Connection) -> dict[str, list[_PendingLap]]:
        rows = conn.execute(
            """
            SELECT id, session_id, lap_number, circuit, car_model, recorded_at, summary_json
            FROM laps
            WHERE uploaded = 0
            ORDER BY session_id, lap_number, id
            """
        )

        grouped: dict[str, list[_PendingLap]] = defaultdict(list)
        for row in rows:
            pending = self._parse_pending_lap(row)
            if pending is None:
                continue
            grouped[pending.session_id].append(pending)
        return dict(grouped)

    def _parse_pending_lap(self, row: sqlite3.Row) -> _PendingLap | None:
        summary_json = row["summary_json"]
        if not summary_json:
            logger.warning(
                "Skipping lap %s/%s because summary_json is empty",
                row["session_id"],
                row["lap_number"],
            )
            return None

        try:
            summary = _load_lap_summary(summary_json)
        except Exception as exc:
            logger.warning(
                "Skipping lap %s/%s because summary_json is invalid: %s",
                row["session_id"],
                row["lap_number"],
                exc,
            )
            return None

        circuit = summary.circuit or _coerce_text(row["circuit"]) or DEFAULT_SESSION_FIELD
        car_model = summary.car_model or _coerce_text(row["car_model"]) or DEFAULT_SESSION_FIELD
        recorded_at = _coerce_datetime(row["recorded_at"]) if row["recorded_at"] else summary.recorded_at

        return _PendingLap(
            row_id=int(row["id"]),
            session_id=str(row["session_id"]),
            lap_number=int(row["lap_number"]),
            summary=summary,
            circuit=circuit,
            car_model=car_model,
            recorded_at=recorded_at,
        )

    def _ensure_session(self, lap: _PendingLap) -> bool:
        if lap.session_id in self._known_sessions:
            return True

        payload = {
            "session_id": lap.session_id,
            "session_type": DEFAULT_SESSION_TYPE,
            "circuit": lap.circuit,
            "car_model": lap.car_model,
            "started_at": lap.recorded_at.isoformat(),
        }
        headers = self._headers()

        try:
            response = httpx.post(
                f"{self._backend_url}/sessions",
                json=payload,
                headers=headers,
                timeout=self._request_timeout_s,
            )
        except httpx.HTTPError as exc:
            logger.warning("Failed to create session %s: %s", lap.session_id, exc)
            return False

        if response.status_code not in (200, 201):
            logger.warning(
                "Failed to create session %s: HTTP %s %s",
                lap.session_id,
                response.status_code,
                response.text.strip(),
            )
            return False

        self._known_sessions.add(lap.session_id)
        return True

    def _upload_lap(self, conn: sqlite3.Connection, lap: _PendingLap) -> bool:
        headers = self._headers()
        try:
            response = httpx.post(
                f"{self._backend_url}/laps",
                json=_dump_lap_summary(lap.summary),
                headers=headers,
                timeout=self._request_timeout_s,
            )
        except httpx.HTTPError as exc:
            logger.warning("Failed to upload lap %s/%s: %s", lap.session_id, lap.lap_number, exc)
            return False

        if response.status_code not in (200, 201):
            logger.warning(
                "Failed to upload lap %s/%s: HTTP %s %s",
                lap.session_id,
                lap.lap_number,
                response.status_code,
                response.text.strip(),
            )
            return False

        try:
            with conn:
                conn.execute("UPDATE laps SET uploaded = 1 WHERE id = ?", (lap.row_id,))
        except sqlite3.Error as exc:
            logger.warning(
                "Uploaded lap %s/%s but failed to mark row uploaded: %s",
                lap.session_id,
                lap.lap_number,
                exc,
            )
            return False

        return True

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key}
