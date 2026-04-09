from __future__ import annotations

import ctypes
import mmap
import os
import time
from ctypes import Structure
from ctypes import wintypes
from typing import Iterable

from .structs import ACCStatus, SPageFileGraphic, SPageFilePhysics, SPageFileStatic

__all__ = ["SharedMemoryReader", "smoke_test"]


FILE_MAP_READ = 0x0004


def _candidate_mapping_names(name: str) -> Iterable[str]:
    yield name
    if "\\" not in name:
        yield fr"Local\{name}"


def _get_kernel32() -> ctypes.WinDLL | None:
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenFileMappingW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.OpenFileMappingW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _mapping_exists(kernel32: ctypes.WinDLL, name: str) -> bool:
    handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, name)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def _read_mapping_bytes(name: str, size: int) -> bytes | None:
    if os.name != "nt":
        return None

    kernel32 = _get_kernel32()
    if kernel32 is None:
        return None

    for candidate in _candidate_mapping_names(name):
        if not _mapping_exists(kernel32, candidate):
            continue
        try:
            with mmap.mmap(-1, size, tagname=candidate, access=mmap.ACCESS_READ) as view:
                return view[:size]
        except OSError:
            continue
    return None


class SharedMemoryReader:
    """Read ACC shared memory pages without mutating them."""

    @staticmethod
    def read(name: str, struct_type: type[Structure]) -> Structure | None:
        if not isinstance(name, str):
            return None

        try:
            if not issubclass(struct_type, Structure):
                return None
        except TypeError:
            return None

        raw = _read_mapping_bytes(name, ctypes.sizeof(struct_type))
        if raw is None or len(raw) < ctypes.sizeof(struct_type):
            return None

        try:
            return struct_type.from_buffer_copy(raw)
        except (BufferError, ValueError, OSError, TypeError):
            return None


def _status_name(value: int) -> str:
    try:
        return ACCStatus(value).name
    except ValueError:
        return str(value)


def smoke_test() -> None:
    """Print a lightweight snapshot from the three ACC shared memory pages."""
    reader = SharedMemoryReader()
    while True:
        physics = reader.read("acpmf_physics", SPageFilePhysics)
        graphics = reader.read("acpmf_graphics", SPageFileGraphic)
        static = reader.read("acpmf_static", SPageFileStatic)

        physics_speed = getattr(physics, "speedKmh", None)
        graphics_status = _status_name(getattr(graphics, "status", -1)) if graphics else "None"
        track = getattr(static, "track", "") if static else ""
        car_model = getattr(static, "carModel", "") if static else ""

        print(
            f"speedKmh={physics_speed!s} status={graphics_status} "
            f"track={track!s} carModel={car_model!s}",
            flush=True,
        )
        time.sleep(1.0)


if __name__ == "__main__":
    smoke_test()
