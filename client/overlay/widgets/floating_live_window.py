from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QObject, Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from overlay.widgets.live_inputs_graph import LiveInputsGraphWidget
from poller.shared_memory import SharedMemoryReader
from poller.structs import SPageFilePhysics

__all__ = ["FloatingLiveWindow"]


class _TitleBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("floatingLiveTitleBar")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(32)

        self._dragging = False

        self._title_label = QLabel("Live Inputs")
        self._title_label.setObjectName("floatingLiveTitleLabel")
        self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._close_button = QToolButton()
        self._close_button.setText("x")
        self._close_button.setToolTip("Close")
        self._close_button.setAutoRaise(True)
        self._close_button.setFixedSize(22, 22)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(6)
        layout.addWidget(self._title_label)
        layout.addStretch(1)
        layout.addWidget(self._close_button)

    def close_button(self) -> QToolButton:
        return self._close_button

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            window = self.window()
            if isinstance(window, FloatingLiveWindow):
                window._begin_drag(event.globalPosition().toPoint())
                window.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            if isinstance(window, FloatingLiveWindow):
                window._drag_to(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            window = self.window()
            if isinstance(window, FloatingLiveWindow):
                window._end_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FloatingLiveWindow(QWidget):
    """Frameless overlay window showing real-time inputs from ACC."""

    def __init__(
        self,
        opacity: float = 0.85,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("floatingLiveWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(max(0.0, min(1.0, opacity)))
        self.resize(800, 400)

        self._drag_offset = QPoint()
        self._dragging = False

        self._surface = QFrame(self)
        self._surface.setObjectName("floatingLiveSurface")

        self._title_bar = _TitleBar(self._surface)
        self._title_bar.close_button().clicked.connect(self.close)

        self._graph_widget = LiveInputsGraphWidget(parent=self._surface)

        surface_layout = QVBoxLayout(self._surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)
        surface_layout.addWidget(self._title_bar)
        surface_layout.addWidget(self._graph_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._surface)

        self._reader = SharedMemoryReader()
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._read_shared_memory)
        self._update_timer.start(30)  # ~30 Hz update rate

        self._apply_style()
        self._install_key_event_filters(self)

    def set_opacity(self, opacity: float) -> None:
        self.setWindowOpacity(max(0.0, min(1.0, opacity)))

    def _read_shared_memory(self) -> None:
        physics = self._reader.read("acpmf_physics", SPageFilePhysics)
        if physics is None:
            return

        frame = {
            "brake": getattr(physics, "brake", 0.0),
            "throttle": getattr(physics, "gas", 0.0),
            "steer_angle": getattr(physics, "steerAngle", 0.0),
            "speed_kmh": getattr(physics, "speedKmh", 0.0),
        }

        self._graph_widget.add_frame(frame)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QFrame#floatingLiveSurface {
                background-color: rgba(15, 18, 24, 220);
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 12px;
            }
            QFrame#floatingLiveTitleBar {
                background-color: rgba(255, 255, 255, 12);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 16);
            }
            QLabel#floatingLiveTitleLabel {
                color: #f2f2f2;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton {
                color: #f2f2f2;
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 10px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 22);
            }
            QCheckBox {
                color: #f2f2f2;
            }
            QLabel {
                color: #f2f2f2;
            }
            """
        )

    def _install_key_event_filters(self, root: QWidget) -> None:
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            return self._handle_key_press(event)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._handle_key_press(event):
            return
        super().keyPressEvent(event)

    def _handle_key_press(self, event: QKeyEvent) -> bool:
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return True

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            modifiers = event.modifiers()
            step = 40 if modifiers & Qt.KeyboardModifier.ShiftModifier else 12
            self._nudge_by_key(key, step)
            event.accept()
            return True

        return False

    def _nudge_by_key(self, key: Qt.Key, step: int) -> None:
        if key == Qt.Key.Key_Left:
            self.move(self.x() - step, self.y())
        elif key == Qt.Key.Key_Right:
            self.move(self.x() + step, self.y())
        elif key == Qt.Key.Key_Up:
            self.move(self.x(), self.y() - step)
        elif key == Qt.Key.Key_Down:
            self.move(self.x(), self.y() + step)
        self._clamp_to_current_screen()

    def _drag_to(self, global_pos: QPoint) -> None:
        if not self._dragging:
            self._begin_drag(global_pos)
        self.move(global_pos - self._drag_offset)
        self._clamp_to_current_screen()

    def _begin_drag(self, global_pos: QPoint) -> None:
        self._dragging = True
        self._drag_offset = global_pos - self.frameGeometry().topLeft()

    def _end_drag(self) -> None:
        self._dragging = False
        self._drag_offset = QPoint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._begin_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_to(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._end_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _current_screen_geometry(self):
        center = self.frameGeometry().center()
        screen = self.screen() or QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return self.frameGeometry()
        return screen.availableGeometry()

    def _clamp_to_current_screen(self) -> None:
        screen_geometry = self._current_screen_geometry()
        frame = self.frameGeometry()

        min_x = screen_geometry.left()
        min_y = screen_geometry.top()
        max_x = screen_geometry.right() - frame.width() + 1
        max_y = screen_geometry.bottom() - frame.height() + 1

        if max_x < min_x:
            max_x = min_x
        if max_y < min_y:
            max_y = min_y

        x = min(max(self.x(), min_x), max_x)
        y = min(max(self.y(), min_y), max_y)
        if x != self.x() or y != self.y():
            self.move(x, y)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._update_timer.stop()
        super().closeEvent(event)
