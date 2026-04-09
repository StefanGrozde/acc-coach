"""ACC Coaching Client -- Phase 1 Scaffolding UI."""
import sys

from PyQt6.QtWidgets import QApplication

from scaffold_ui.connection_tester import ConnectionTesterWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = ConnectionTesterWindow()
    window.setWindowTitle("ACC Coaching -- Backend Connection Tester")
    window.resize(500, 300)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

