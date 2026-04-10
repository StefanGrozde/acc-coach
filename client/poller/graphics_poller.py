from __future__ import annotations

import queue
import threading
import time

from .shared_memory import SharedMemoryReader
from .structs import SPageFileGraphic

__all__ = ["GraphicsPollerThread"]


class GraphicsPollerThread(threading.Thread):
    def __init__(self, output_queue: queue.Queue[dict[str, object]]) -> None:
        super().__init__(daemon=True, name="GraphicsPollerThread")
        self._output_queue = output_queue
        self._reader = SharedMemoryReader()
        self._interval_s = 1.0 / 25.0

    def _build_frame(self, graphics: SPageFileGraphic) -> dict[str, object]:
        return {
            "packet_id": int(graphics.packetId),
            "completed_laps": int(graphics.completedLaps),
            "session_time_left": float(graphics.sessionTimeLeft),
            "current_sector_index": int(graphics.currentSectorIndex),
            "last_sector_time": int(graphics.lastSectorTime),
            "track_grip_status": int(graphics.trackGripStatus),
            "rain_intensity": int(graphics.rainIntensity),
            "status": int(graphics.status),
            "penalty": int(graphics.penalty),
        }

    def run(self) -> None:
        while True:
            started_at = time.perf_counter()
            try:
                graphics = self._reader.read("acpmf_graphics", SPageFileGraphic)
                if graphics is None:
                    continue

                self._output_queue.put(self._build_frame(graphics))
            except Exception:
                pass
            finally:
                elapsed = time.perf_counter() - started_at
                remaining = self._interval_s - elapsed
                if remaining > 0:
                    time.sleep(remaining)
