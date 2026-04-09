from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DIST_NAME = "acc-shared"
DIST_NAME_NORMALIZED = "acc_shared"
VERSION = "0.1.0"
WHEEL_FILENAME = f"{DIST_NAME_NORMALIZED}-{VERSION}-py3-none-any.whl"
DIST_INFO_DIR = f"{DIST_NAME_NORMALIZED}-{VERSION}.dist-info"
PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent


def get_requires_for_build_wheel(config_settings: object | None = None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings: object | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings: object | None = None) -> str:
    _write_metadata(Path(metadata_directory))
    return DIST_INFO_DIR


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings: object | None = None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(
    wheel_directory: str,
    config_settings: object | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_wheel(Path(wheel_directory), editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: object | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_wheel(Path(wheel_directory), editable=True)


def _build_wheel(wheel_directory: Path, editable: bool) -> str:
    wheel_directory.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_directory / WHEEL_FILENAME

    files: dict[str, bytes] = {}
    files[f"{DIST_INFO_DIR}/METADATA"] = _metadata_text().encode("utf-8")
    files[f"{DIST_INFO_DIR}/WHEEL"] = _wheel_text().encode("utf-8")
    files[f"{DIST_INFO_DIR}/top_level.txt"] = b"shared\n"
    if editable:
        files[f"{DIST_NAME_NORMALIZED}.pth"] = (str(REPO_ROOT) + os.linesep).encode("utf-8")

    record_lines = []
    for arcname, payload in files.items():
        record_lines.append(_record_line(arcname, payload))
    record_lines.append(f"{DIST_INFO_DIR}/RECORD,,")
    files[f"{DIST_INFO_DIR}/RECORD"] = ("\n".join(record_lines) + "\n").encode("utf-8")

    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED) as zf:
        for arcname, payload in files.items():
            zf.writestr(arcname, payload)

    return wheel_path.name


def _write_metadata(metadata_directory: Path) -> None:
    dist_info = metadata_directory / DIST_INFO_DIR
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "top_level.txt").write_text("shared\n", encoding="utf-8")


def _metadata_text() -> str:
    return "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {DIST_NAME}",
            f"Version: {VERSION}",
            "Requires-Python: >=3.11",
            "",
        ]
    )


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: codex-custom-backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _record_line(arcname: str, payload: bytes) -> str:
    digest = hashlib.sha256(payload).digest()
    encoded_digest = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{arcname},sha256={encoded_digest},{len(payload)}"
