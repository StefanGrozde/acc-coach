"""PyQt6 scaffold window for testing backend connectivity."""
from __future__ import annotations

from pathlib import Path
import tomllib

import httpx
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DEFAULT_URL = "http://localhost:8000/api/v1"
DEFAULT_API_KEY = "your-secret-key-here"


def _load_config() -> dict[str, str]:
    config_path = Path(__file__).resolve().parents[1] / "config.toml"
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {"url": DEFAULT_URL, "api_key": DEFAULT_API_KEY}

    backend = data.get("backend", {}) if isinstance(data, dict) else {}
    url = backend.get("url", DEFAULT_URL) if isinstance(backend, dict) else DEFAULT_URL
    api_key = backend.get("api_key", DEFAULT_API_KEY) if isinstance(backend, dict) else DEFAULT_API_KEY
    return {"url": str(url), "api_key": str(api_key)}


def _normalize_base_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return DEFAULT_URL
    return cleaned.rstrip("/")


class ConnectionTesterWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        config = _load_config()

        self.url_input = QLineEdit(_normalize_base_url(config["url"]))
        self.api_key_input = QLineEdit(config["api_key"])
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont("Courier New"))
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        health_button = QPushButton("Test Health")
        auth_button = QPushButton("Test Auth")
        health_button.clicked.connect(self.test_health)
        auth_button.clicked.connect(self.test_auth)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Backend URL:"))
        layout.addWidget(self.url_input)
        layout.addWidget(QLabel("API Key:"))
        layout.addWidget(self.api_key_input)

        button_row = QHBoxLayout()
        button_row.addWidget(health_button)
        button_row.addWidget(auth_button)
        layout.addLayout(button_row)

        layout.addWidget(self.status_label)

    def _status_text(self, title: str, response: httpx.Response | None = None, error: Exception | None = None) -> str:
        if error is not None:
            return f"{title}\nError: {error}"
        if response is None:
            return f"{title}\nNo response received."

        body = response.text.strip() or "<empty body>"
        return f"{title}\nHTTP {response.status_code}\n{body}"

    def test_health(self) -> None:
        url = f"{_normalize_base_url(self.url_input.text())}/health"
        try:
            response = httpx.get(url, timeout=10.0)
        except httpx.HTTPError as exc:
            self.status_label.setText(self._status_text("Health check failed", error=exc))
            return
        self.status_label.setText(self._status_text("Health check result", response=response))

    def test_auth(self) -> None:
        url = f"{_normalize_base_url(self.url_input.text())}/sessions/nonexistent-test"
        headers = {"X-API-Key": self.api_key_input.text()}
        try:
            response = httpx.get(url, headers=headers, timeout=10.0)
        except httpx.HTTPError as exc:
            self.status_label.setText(self._status_text("Auth check failed", error=exc))
            return
        if response.status_code == 404:
            title = "Auth check passed"
        elif response.status_code == 401:
            title = "Auth check failed"
        else:
            title = "Auth check result"
        self.status_label.setText(self._status_text(title, response=response))
