from __future__ import annotations

import queue
import threading
import time
from collections.abc import Sequence

from .shared_memory import SharedMemoryReader
from .structs import SPageFileGraphic, SPageFilePhysics

__all__ = ["PhysicsPollerThread"]


def _to_list(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


class PhysicsPollerThread(threading.Thread):
    def __init__(self, output_queue: queue.Queue[dict[str, object]]) -> None:
        super().__init__(daemon=True, name="PhysicsPollerThread")
        self._output_queue = output_queue
        self._reader = SharedMemoryReader()
        self._interval_s = 1.0 / 60.0

    def _build_frame(self, physics: SPageFilePhysics, distance_m: float | None) -> dict[str, object]:
        return {
            "packet_id": int(physics.packetId),
            "speed_kmh": float(physics.speedKmh),
            "brake": float(physics.brake),
            "throttle": float(physics.throttle),
            "steer": float(physics.steerAngle),
            "gear": int(physics.gear),
            "rpms": int(physics.rpms),
            "abs": float(getattr(physics, "abs", 0.0)),
            "tc": float(physics.tc),
            "fuel": float(physics.fuel),
            "tyre_temp": _to_list(physics.tyreTemp),
            "tyre_pressure": _to_list(physics.tyrePressure),
            "wheel_slip": _to_list(physics.wheelSlip),
            "tyreWear": _to_list(physics.tyreWear),
            "tyreCoreTemperature": _to_list(physics.tyreCoreTemperature),
            "airTemp": float(physics.airTemp),
            "roadTemp": float(physics.roadTemp),
            "distance_m": distance_m,
        }

    def run(self) -> None:
        while True:
            started_at = time.perf_counter()
            try:
                physics = self._reader.read("acpmf_physics", SPageFilePhysics)
                if physics is None:
                    continue

                graphics = self._reader.read("acpmf_graphics", SPageFileGraphic)
                distance_m = float(graphics.distanceTraveled) if graphics is not None else None
                self._output_queue.put(self._build_frame(physics, distance_m))
            except Exception:
                pass
            finally:
                elapsed = time.perf_counter() - started_at
                remaining = self._interval_s - elapsed
                if remaining > 0:
                    time.sleep(remaining)
