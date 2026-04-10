from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
import tomllib

import httpx
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

__all__ = ["BackendDataViewer"]


logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"
DEFAULT_API_KEY = "your-secret-key-here"


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config.toml"


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "acc_coach.db"


def _normalize_base_url(url: str) -> str:
    cleaned = url.strip()
    return cleaned.rstrip("/") if cleaned else DEFAULT_BACKEND_URL


def _coerce_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            try:
                return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def _format_datetime(value: Any) -> str:
    parsed = _coerce_datetime(value)
    if parsed is None:
        return "Unknown date"
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_lap_time(value: Any) -> str:
    if value in (None, ""):
        return "Unknown"
    try:
        lap_time_ms = int(float(value))
    except (TypeError, ValueError):
        return "Unknown"
    if lap_time_ms < 0:
        return "Unknown"

    minutes, remainder_ms = divmod(lap_time_ms, 60_000)
    seconds, milliseconds = divmod(remainder_ms, 1_000)
    if minutes:
        return f"{minutes:d}:{seconds:02d}.{milliseconds:03d}"
    return f"{seconds:d}.{milliseconds:03d}"


def _format_valid_flag(value: Any) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return "Yes"
        if normalized in {"0", "false", "no", "n"}:
            return "No"
    return "Yes" if bool(value) else "No"


def _format_sector_times(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    parts: list[str] = []
    for index, sector in enumerate(value, start=1):
        try:
            sector_ms = int(float(sector))
        except (TypeError, ValueError):
            continue
        parts.append(f"S{index} {_format_lap_time(sector_ms)}")
    return " | ".join(parts) if parts else "-"


def _load_backend_config(config_path: Path) -> dict[str, str]:
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {"url": DEFAULT_BACKEND_URL, "api_key": DEFAULT_API_KEY}

    backend = data.get("backend", {}) if isinstance(data, dict) else {}
    if not isinstance(backend, dict):
        backend = {}

    return {
        "url": str(backend.get("url", DEFAULT_BACKEND_URL)),
        "api_key": str(backend.get("api_key", DEFAULT_API_KEY)),
    }


class BackendDataViewer(QWidget):
    """Browse uploaded sessions and laps from the backend."""

    def __init__(
        self,
        config_path: Path | None = None,
        db_path: Path | None = None,
        backend_url: str | None = None,
        api_key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._config_path = Path(config_path) if config_path is not None else _default_config_path()
        config = _load_backend_config(self._config_path)

        self._backend_url = _normalize_base_url(backend_url or config["url"])
        self._api_key = api_key if api_key is not None else config["api_key"]
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()

        self._sessions: list[dict[str, Any]] = []
        self._laps: list[dict[str, Any]] = []
        self._graph_window: QWidget | None = None
        self._local_laps: list[dict[str, Any]] = []

        self._status_label = QLabel("Ready.")
        self._status_label.setWordWrap(True)

        self._refresh_button = QPushButton("Refresh (Remote)")
        self._refresh_button.clicked.connect(self.refresh_sessions)

        self._local_button = QPushButton("Load Local Laps")
        self._local_button.clicked.connect(self.load_local_laps)

        self._sessions_list = QListWidget()
        self._sessions_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._sessions_list.currentItemChanged.connect(self._handle_session_changed)

        self._laps_table = QTableWidget(0, 4)
        self._laps_table.setHorizontalHeaderLabels(["Lap", "Time", "Valid", "Sectors"])
        self._laps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._laps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._laps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._laps_table.setAlternatingRowColors(True)
        self._laps_table.verticalHeader().setVisible(False)
        self._laps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._laps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._laps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._laps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._laps_table.cellDoubleClicked.connect(self._open_lap_from_row)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Sessions"))
        left_layout.addWidget(self._sessions_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Laps"))
        right_layout.addWidget(self._laps_table)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        controls = QHBoxLayout()
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._local_button)
        controls.addStretch(1)
        controls.addWidget(self._status_label)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(splitter)

        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        previous_session_id = self._current_session_id()
        try:
            sessions = self._fetch_sessions()
        except Exception as exc:
            logger.warning("Failed to load sessions: %s", exc)
            self._set_status(f"Failed to load sessions: {exc}")
            return

        self._sessions = sessions
        self._populate_sessions(previous_session_id)
        if self._sessions and self._sessions_list.currentRow() < 0:
            self._sessions_list.setCurrentRow(0)
        if not self._sessions:
            self._set_status("No sessions available.")
        else:
            self._set_status(f"Loaded {len(self._sessions)} sessions.")

    def _fetch_sessions(self) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self._backend_url}/sessions",
            headers=self._headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def _fetch_laps(self, session_id: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self._backend_url}/sessions/{session_id}/laps",
            headers=self._headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def load_local_laps(self) -> None:
        import sqlite3

        try:
            laps = self._fetch_local_laps()
        except Exception as exc:
            logger.warning("Failed to load local laps: %s", exc)
            self._set_status(f"Failed to load local laps: {exc}")
            return

        self._laps = laps
        self._populate_laps(laps)
        if not laps:
            self._set_status("No local laps found. Drive a lap in ACC to record data.")
        else:
            self._set_status(f"Loaded {len(laps)} local laps from SQLite.")

    def _fetch_local_laps(self) -> list[dict[str, Any]]:
        import sqlite3

        query = """
            SELECT session_id, lap_number, lap_time_ms, is_valid,
                   circuit, car_model, recorded_at, sector_times_ms
            FROM laps
            ORDER BY recorded_at DESC, session_id DESC, lap_number DESC
        """

        laps = []
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute(query)
                for row in cursor.fetchall():
                    laps.append({
                        "session_id": row[0],
                        "lap_number": row[1],
                        "lap_time_ms": row[2],
                        "is_valid": bool(row[3]),
                        "circuit": row[4],
                        "car_model": row[5],
                        "recorded_at": row[6],
                        "sector_times_ms": self._parse_sector_json(row[7]),
                    })
                return laps
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error: {exc}") from exc

    @staticmethod
    def _parse_sector_json(value: str | None) -> list[int]:
        if not value:
            return []
        try:
            import json
            data = json.loads(value)
            if isinstance(data, list):
                return [int(x) for x in data]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return []

    def _populate_sessions(self, preferred_session_id: str | None = None) -> None:
        self._sessions_list.blockSignals(True)
        selected_index = 0 if self._sessions else -1
        try:
            self._sessions_list.clear()
            for session in self._sessions:
                label = self._session_label(session)
                item = QListWidgetItem(label)
                item.setToolTip(self._session_tooltip(session))
                item.setData(Qt.ItemDataRole.UserRole, session)
                self._sessions_list.addItem(item)

            if preferred_session_id is not None:
                for index, session in enumerate(self._sessions):
                    if _coerce_text(session.get("session_id")) == preferred_session_id:
                        selected_index = index
                        break
        finally:
            self._sessions_list.blockSignals(False)

        if selected_index >= 0 and self._sessions:
            self._sessions_list.setCurrentRow(selected_index)

    def _handle_session_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            self._laps = []
            self._populate_laps([])
            return

        session = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(session, dict):
            self._laps = []
            self._populate_laps([])
            return

        session_id = _coerce_text(session.get("session_id"))
        if not session_id:
            self._laps = []
            self._populate_laps([])
            return

        self._set_status(f"Loading laps for {self._session_label(session)}...")
        try:
            laps = self._fetch_laps(session_id)
        except Exception as exc:
            logger.warning("Failed to load laps for %s: %s", session_id, exc)
            self._laps = []
            self._populate_laps([])
            self._set_status(f"Failed to load laps: {exc}")
            return

        self._laps = laps
        self._populate_laps(laps)
        self._set_status(f"Loaded {len(laps)} laps for {self._session_label(session)}.")

    def _populate_laps(self, laps: list[dict[str, Any]]) -> None:
        self._laps_table.setRowCount(0)
        self._laps_table.setRowCount(len(laps))

        for row_index, lap in enumerate(laps):
            lap_number = lap.get("lap_number", row_index + 1)
            values = [
                str(lap_number),
                _format_lap_time(lap.get("lap_time_ms")),
                _format_valid_flag(lap.get("is_valid")),
                _format_sector_times(lap.get("sector_times_ms")),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, lap)
                if column_index in (0, 1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._laps_table.setItem(row_index, column_index, item)

        self._laps_table.resizeRowsToContents()

    def _open_lap_from_row(self, row: int, column: int) -> None:
        del column
        if row < 0 or row >= len(self._laps):
            return

        lap = self._laps[row]
        session_id = _coerce_text(lap.get("session_id"))
        if not session_id:
            self._set_status("Selected lap is missing a session_id.")
            return

        lap_number = lap.get("lap_number")
        try:
            lap_number_int = int(lap_number)
        except (TypeError, ValueError):
            self._set_status("Selected lap is missing a valid lap number.")
            return

        try:
            self._show_lap_graph(session_id, lap_number_int)
        except Exception as exc:
            logger.warning("Failed to open lap graph for %s/%s: %s", session_id, lap_number_int, exc)
            self._set_status(f"Failed to open graph: {exc}")

    def _show_lap_graph(self, session_id: str, lap_number: int) -> None:
        if not session_id:
            raise ValueError("session_id is required")

        try:
            from overlay.widgets.floating_graph_window import FloatingGraphWindow
        except Exception as exc:  # pragma: no cover - depends on optional Qt/graph runtime.
            raise RuntimeError(f"Graph window unavailable: {exc}") from exc

        window = self._graph_window if isinstance(self._graph_window, FloatingGraphWindow) else None
        if window is None:
            window = FloatingGraphWindow(db_path=self._db_path)
            self._graph_window = window

        window.set_lap(session_id, lap_number)
        window.show()
        window.raise_()
        window.activateWindow()
        self._set_status(f"Opened lap {lap_number} for {session_id} in the graph window.")

    def _current_session(self) -> dict[str, Any] | None:
        current_item = self._sessions_list.currentItem()
        if current_item is None:
            return None
        session = current_item.data(Qt.ItemDataRole.UserRole)
        return session if isinstance(session, dict) else None

    def _current_session_id(self) -> str | None:
        session = self._current_session()
        if session is None:
            return None
        session_id = _coerce_text(session.get("session_id"))
        return session_id or None

    def _session_label(self, session: dict[str, Any]) -> str:
        circuit = _coerce_text(session.get("circuit"), "Unknown circuit")
        car_model = _coerce_text(session.get("car_model"), "Unknown car")
        started_at = _format_datetime(session.get("started_at") or session.get("created_at"))
        return f"{circuit} | {car_model} | {started_at}"

    def _session_tooltip(self, session: dict[str, Any]) -> str:
        session_id = _coerce_text(session.get("session_id"), "unknown-session")
        session_type = _coerce_text(session.get("session_type"), "Unknown type")
        return f"Session {session_id}\nType: {session_type}\n{self._session_label(session)}"

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key}

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._graph_window is not None:
            self._graph_window.close()
            self._graph_window = None
        super().closeEvent(event)
