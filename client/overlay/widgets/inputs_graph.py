from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget

__all__ = ["InputsGraphWidget"]


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "acc_coach.db"


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class InputsGraphWidget(QWidget):
    """Plot lap brake, throttle, and speed traces against distance."""

    def __init__(self, db_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()

        self._plot_widget = pg.PlotWidget()
        self._plot_item = self._plot_widget.getPlotItem()
        self._plot_item.showGrid(x=True, y=True, alpha=0.25)
        self._plot_item.setLabel("bottom", "Distance", units="m")
        self._plot_item.setLabel("left", "Input", units="0-1")
        self._plot_item.showAxis("right")

        self._speed_axis = self._plot_item.getAxis("right")
        self._speed_axis.setLabel("Speed", units="km/h")

        self._speed_view = pg.ViewBox()
        self._plot_item.scene().addItem(self._speed_view)
        self._speed_axis.linkToView(self._speed_view)
        self._speed_view.setXLink(self._plot_item.vb)
        self._plot_item.vb.sigResized.connect(self._update_speed_view)

        self._brake_curve = self._plot_item.plot(
            [],
            [],
            pen=pg.mkPen((220, 40, 40), width=2),
            fillLevel=0.0,
            brush=pg.mkBrush(220, 40, 40, 60),
        )
        self._throttle_curve = self._plot_item.plot(
            [],
            [],
            pen=pg.mkPen((40, 180, 80), width=2),
            fillLevel=0.0,
            brush=pg.mkBrush(40, 180, 80, 60),
        )
        self._speed_curve = pg.PlotDataItem(pen=pg.mkPen((50, 120, 255), width=2))
        self._speed_view.addItem(self._speed_curve)

        self._plot_item.setYRange(0.0, 1.05)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot_widget)

        self._update_speed_view()

    def set_lap(self, session_id: str, lap_number: int) -> None:
        rows = self._load_rows(session_id, lap_number)

        if not rows:
            self._set_empty_state()
            return

        distances: list[float] = []
        brake_values: list[float] = []
        throttle_values: list[float] = []
        speed_values: list[float] = []

        for distance, brake, throttle, speed in rows:
            if distance is None:
                continue
            distances.append(_coerce_float(distance))
            brake_values.append(max(0.0, min(1.0, _coerce_float(brake))))
            throttle_values.append(max(0.0, min(1.0, _coerce_float(throttle))))
            speed_values.append(max(0.0, _coerce_float(speed)))

        if not distances:
            self._set_empty_state()
            return

        self._brake_curve.setData(distances, brake_values)
        self._throttle_curve.setData(distances, throttle_values)
        self._speed_curve.setData(distances, speed_values)

        self._plot_item.setXRange(min(distances), max(distances), padding=0.02)
        self._plot_item.setYRange(0.0, 1.05)

        speed_min = min(speed_values)
        speed_max = max(speed_values)
        if speed_min == speed_max:
            pad = 5.0 if speed_max == 0.0 else max(5.0, speed_max * 0.05)
            self._speed_view.setYRange(speed_min - pad, speed_max + pad, padding=0.0)
        else:
            self._speed_view.setYRange(speed_min, speed_max, padding=0.08)

        self._update_speed_view()

    def _load_rows(self, session_id: str, lap_number: int) -> list[tuple[Any, Any, Any, Any]]:
        query = """
            SELECT distance_m, brake, throttle, speed_kmh
            FROM frames
            WHERE session_id = ? AND lap_number = ?
            ORDER BY timestamp_ms ASC, id ASC
        """

        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(query, (session_id, lap_number))
                return list(cursor.fetchall())
        except sqlite3.Error:
            return []

    def _set_empty_state(self) -> None:
        self._brake_curve.setData([], [])
        self._throttle_curve.setData([], [])
        self._speed_curve.setData([], [])
        self._plot_item.setXRange(0.0, 1.0, padding=0.0)
        self._plot_item.setYRange(0.0, 1.05)
        self._speed_view.setYRange(0.0, 1.0, padding=0.0)
        self._update_speed_view()

    def _update_speed_view(self) -> None:
        self._speed_view.setGeometry(self._plot_item.vb.sceneBoundingRect())
        self._speed_view.linkedViewChanged(self._plot_item.vb, self._speed_view.XAxis)
