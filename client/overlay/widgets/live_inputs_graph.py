from __future__ import annotations

from collections import deque
from typing import Any

import pyqtgraph as pg
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

__all__ = ["LiveInputsGraphWidget"]


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class LiveInputsGraphWidget(QWidget):
    """Real-time rolling plot of brake, throttle, and steering inputs."""

    def __init__(
        self,
        window_seconds: float = 30.0,
        update_interval_ms: int = 50,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._window_seconds = window_seconds
        self._max_points = int(window_seconds * 1000 / update_interval_ms)

        self._timestamps = deque(maxlen=self._max_points)
        self._brake_values = deque(maxlen=self._max_points)
        self._throttle_values = deque(maxlen=self._max_points)
        self._steer_values = deque(maxlen=self._max_points)

        self._plot_widget = pg.PlotWidget()
        self._plot_item = self._plot_widget.getPlotItem()
        self._plot_item.showGrid(x=True, y=True, alpha=0.25)
        self._plot_item.setLabel("bottom", "Time", units="s")
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
        self._steer_curve = self._plot_item.plot(
            [],
            [],
            pen=pg.mkPen((240, 200, 30), width=2),
        )
        self._speed_curve = pg.PlotDataItem(pen=pg.mkPen((50, 120, 255), width=2))
        self._speed_view.addItem(self._speed_curve)

        self._legend = self._plot_item.addLegend(offset=(10, 10))
        self._legend.addItem(self._brake_curve, "Brake")
        self._legend.addItem(self._throttle_curve, "Throttle")
        self._legend.addItem(self._steer_curve, "Steering")
        self._legend.addItem(self._speed_curve, "Speed")

        self._plot_item.setYRange(0.0, 1.05)

        self._current_speed_label = QLabel("Speed: -- km/h")
        self._current_throttle_label = QLabel("Throttle: --%")
        self._current_brake_label = QLabel("Brake: --%")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self._current_speed_label)
        controls.addWidget(self._current_throttle_label)
        controls.addWidget(self._current_brake_label)
        controls.addStretch(1)

        self._steer_toggle = QCheckBox("Show steering")
        self._steer_toggle.setChecked(True)
        self._steer_toggle.toggled.connect(self._steer_curve.setVisible)
        controls.addWidget(self._steer_toggle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self._plot_widget)

        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_plot)
        self._update_timer.start(update_interval_ms)

        self._start_time = None
        self._update_speed_view()

    def add_frame(self, frame: dict[str, Any]) -> None:
        """Add a new frame to the live data buffers."""
        import time

        if self._start_time is None:
            self._start_time = time.time()

        elapsed = time.time() - self._start_time
        brake = max(0.0, min(1.0, _coerce_float(frame.get("brake"))))
        throttle = max(0.0, min(1.0, _coerce_float(frame.get("throttle"))))
        steer_raw = max(-1.0, min(1.0, _coerce_float(frame.get("steer_angle"))))
        steer = (steer_raw + 1.0) / 2.0
        speed = max(0.0, _coerce_float(frame.get("speed_kmh")))

        self._timestamps.append(elapsed)
        self._brake_values.append(brake)
        self._throttle_values.append(throttle)
        self._steer_values.append(steer)

        self._current_speed_label.setText(f"Speed: {speed:.1f} km/h")
        self._current_throttle_label.setText(f"Throttle: {throttle*100:.0f}%")
        self._current_brake_label.setText(f"Brake: {brake*100:.0f}%")

    def _update_plot(self) -> None:
        """Update the plot curves with current buffer data."""
        if not self._timestamps:
            return

        timestamps = list(self._timestamps)
        brakes = list(self._brake_values)
        throttles = list(self._throttle_values)
        steers = list(self._steer_values)

        self._brake_curve.setData(timestamps, brakes)
        self._throttle_curve.setData(timestamps, throttles)
        self._steer_curve.setData(timestamps, steers)
        self._steer_curve.setVisible(self._steer_toggle.isChecked())

        if timestamps:
            self._plot_item.setXRange(max(0, timestamps[-1] - self._window_seconds), timestamps[-1] + 1, padding=0.02)

    def set_speed(self, speed_kmh: float) -> None:
        """Update the current speed value."""
        self._speed_curve.setData([self._timestamps[-1]] if self._timestamps else [], [speed_kmh])

    def _update_speed_view(self) -> None:
        self._speed_view.setGeometry(self._plot_item.vb.sceneBoundingRect())
        self._speed_view.linkedViewChanged(self._plot_item.vb, self._speed_view.XAxis)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._update_timer.stop()
        super().closeEvent(event)
