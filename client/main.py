"""ACC Coaching Client -- Main Application."""
import sys
from pathlib import Path
from queue import Queue
import threading
import time

# Add project root to Python path for shared package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication

from overlay.data_viewer import BackendDataViewer
from poller.graphics_poller import GraphicsPollerThread
from poller.physics_poller import PhysicsPollerThread
from recorder.lap_recorder import RecorderThread
from store.database import init_db
from sync.uploader import UploaderThread


def main() -> int:
    # Initialize SQLite database
    db_path = Path.cwd() / "data" / "acc_coach.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    # Create queues for inter-thread communication
    physics_queue: Queue = Queue()
    graphics_queue: Queue = Queue()

    # Start poller threads (daemon = auto-kill on exit)
    physics_poller = PhysicsPollerThread(physics_queue)
    physics_poller.daemon = True
    physics_poller.start()

    graphics_poller = GraphicsPollerThread(graphics_queue)
    graphics_poller.daemon = True
    graphics_poller.start()

    # Start recorder thread (consumes both queues)
    recorder = RecorderThread(physics_queue, graphics_queue, db_path)
    recorder.daemon = True
    recorder.start()

    # Start uploader thread (polls SQLite for pending uploads)
    uploader = UploaderThread(db_path)
    uploader.daemon = True
    uploader.start()

    # Launch Qt UI (blocking call)
    app = QApplication(sys.argv)
    window = BackendDataViewer(db_path=db_path)
    window.setWindowTitle("ACC Coaching -- Data Viewer")
    window.resize(1200, 800)
    window.show()

    # Keep references to threads so they don't get garbage collected
    app.poller_threads = [physics_poller, graphics_poller, recorder, uploader]

    # Ensure clean shutdown on exit
    def cleanup():
        recorder.stop()
        recorder.join(timeout=2.0)
        uploader.stop()
        uploader.join(timeout=2.0)

    app.aboutToQuit.connect(cleanup)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
