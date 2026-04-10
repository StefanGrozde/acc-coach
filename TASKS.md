# TASKS.md

## Completed Sprints

### Sprint 1 — Infrastructure Foundation ✓
Branch: `sprint-1-infrastructure` → Merged to `main`
Status: DONE (2026-04-10)
PR: https://github.com/StefanGrozde/acc-coach/pull/1

**Summary**: Established core infrastructure for both backend API and client application, including Docker deployment, PostgreSQL database with migrations, FastAPI routers with authentication, shared Pydantic models, and a PyQt6 connection testing UI.

**Tasks Completed**:
- T1.1 — Shared models package (`shared/`) with all Pydantic v2 models from SPEC.md (WheelData, CornerSummary, LapSummary, SessionSummary, AnalysisRequest, CornerFeedback, AnalysisResult, CornerDelta, LapDeltaHeader, TailAggregate, DeltaReport)
- T1.2 — Docker Compose setup with FastAPI/gunicorn backend and PostgreSQL 15, including `.env.example` configuration
- T1.3 — Async SQLAlchemy database session, Alembic migrations, and initial schema (sessions, laps, analyses, reference_laps tables with indexes)
- T1.4 — FastAPI application skeleton with API key authentication middleware, CORS, and structlog configuration
- T1.5 — Full API routers (sessions, laps, analysis, reference-laps) with CRUD endpoints and `X-API-Key` auth; analysis POST returns 501 (Phase 3)
- T1.6 — PyQt6 connection testing UI (`client/scaffold_ui/`) for backend connectivity verification

**Key Files Created**:
- `shared/models.py`, `shared/pyproject.toml`
- `docker-compose.yml`, `backend/Dockerfile`, `backend/requirements.txt`
- `backend/db/session.py`, `backend/models/orm.py`, `backend/db/migrations/versions/20260410_initial.py`
- `backend/main.py`, `backend/auth.py`, `backend/routers/*.py`
- `client/main.py`, `client/config.toml`, `client/scaffold_ui/connection_tester.py`

**P1 Bugs Fixed (Post-Review)**:
- LapSummary datetime serialization: Changed `payload.model_dump()` → `payload.model_dump(mode="json")` in `laps.py`
- Session creation race condition: Replaced check-then-insert with atomic IntegrityError-based upsert pattern

**Deployment**: Verified on remote Ubuntu server with PostgreSQL, Docker Compose, and all API endpoints functional.

---

## Sprint 2 — Client Telemetry & Visualization
Branch: `sprint-2-client-telemetry`
Status: PENDING

### T2.1 — ACC Shared Memory Reader
Status: PENDING
**Context:** ACC exposes three memory-mapped files: `acpmf_physics` (~60Hz), `acpmf_graphics` (~25Hz), `acpmf_static` (once). Uses `ctypes.Structure` + `mmap` via `win32api`. Read-only — never write. See SPEC.md 7.1–7.2.
**Files:** CREATE `client/poller/structs.py`, CREATE `client/poller/shared_memory.py`
**Steps:**
1. Define `SPageFilePhysics`, `SPageFileGraphic`, `SPageFileStatic` as `ctypes.Structure` subclasses matching ACC SDK layout (fields: `speedKmh`, `brake`, `throttle`, `steerAngle`, `gear`, `rpms`, `wheelSlip`, `abs`, `tc`, `fuel`, `tyreTemp`, `tyrePressure`, `numberOfLaps`, `completedLaps`, `distanceTraveled`, `sessionTimeLeft`, `status`, `penalty`, `track`, `carModel`, etc.)
2. Implement `SharedMemoryReader.read(name: str, struct_type) -> Structure | None` that calls `win32file.CreateFileMapping` / `mmap.mmap`, returns `None` if file not found (game not running)
3. Add a simple smoke test: loop that reads all three structs and prints `speedKmh` + `status` every second
**Acceptance:**
- [ ] Structs parse without error when ACC is running
- [ ] Returns `None` gracefully when ACC is not running (no crash)

### T2.2 — Poller Threads & Queue Plumbing
Status: PENDING
**Depends on:** T2.1
**Context:** Two daemon threads push frames into `queue.Queue`. `PhysicsPollerThread` reads `acpmf_physics` at ~60Hz, `GraphicsPollerThread` reads `acpmf_graphics` at ~25Hz. Each frame is a dict with `packet_id` + relevant fields.
**Files:** CREATE `client/poller/physics_poller.py`, CREATE `client/poller/graphics_poller.py`, MODIFY `client/poller/__init__.py`
**Steps:**
1. Create `PhysicsPollerThread(threading.Thread)` — takes a `queue.Queue`, loops reading `SPageFilePhysics`, pushes `{"packet_id": ..., "speed_kmh": ..., "brake": ..., "throttle": ..., "steer": ..., "gear": ..., "rpms": ..., "abs": ..., "tc": ..., "fuel": ..., "tyre_temp": ..., "tyre_pressure": ..., "wheel_slip": ..., "distance_m": ...}` to queue, sleeps 1/60s
2. Create `GraphicsPollerThread(threading.Thread)` — pushes `{"packet_id": ..., "completed_laps": ..., "session_time_left": ..., "status": ..., "penalty": ...}` at 1/25s
3. Both threads set `daemon=True`, catch all exceptions silently, and retry on `None` reads (game not running)
**Acceptance:**
- [ ] Both threads start and populate queues without errors
- [ ] Queues receive frames when ACC is live, stay empty without crashing when ACC is absent

### T2.3 — SQLite Frame Store & Schema
Status: PENDING
**Context:** Local SQLite database at `client/data/acc_coach.db`. Tables: `frames` (raw physics ticks), `laps` (aggregated LapSummary JSON), `reference_laps`. See SPEC.md 5.2 for exact DDL.
**Files:** CREATE `client/store/database.py`
**Steps:**
1. Implement `init_db(db_path: Path)` — creates tables per SPEC.md 5.2 DDL (`frames`, `laps`, `reference_laps`) if not exist
2. Implement `insert_frame(conn, session_id, lap_number, packet_id, timestamp_ms, fields: dict)` — inserts one row, `fields` stored as `raw_json`
3. Implement `mark_lap_summary(conn, session_id, lap_number, lap_time_ms, is_valid, circuit, car_model, summary_json)` — upserts into `laps` table with `uploaded=0`
**Acceptance:**
- [ ] `init_db` creates all three tables with correct indexes
- [ ] Frames and laps can be written/read round-trip

### T2.4 — Lap Recorder Thread
Status: PENDING
**Depends on:** T2.2, T2.3
**Context:** Consumes both physics and graphics queues. Detects new lap when `completedLaps` increments and `status == ACC_LIVE`. Writes frames during the lap, finalizes lap on boundary.
**Files:** CREATE `client/recorder/lap_recorder.py`
**Steps:**
1. `RecorderThread` drains physics queue, buffers frames under current `(session_id, lap_number)`. Track `current_lap`, `last_completed_laps`, `session_start_time`
2. On `completedLaps` increment: flush buffered frames to SQLite via `insert_frame`, finalize lap with `mark_lap_summary` (placeholder summary — T2.5 fills real data)
3. Generate `session_id` as `uuid4().hex` on first frame; reset on new ACC session detection (`status` change from non-live to live)
**Acceptance:**
- [ ] Frame data written to SQLite during a lap
- [ ] Lap boundary detected correctly (new row in `laps` table)
- [ ] Handles mid-session start (partial first lap recorded)

### T2.5 — Lap Summarizer
Status: PENDING
**Depends on:** T2.3
**Context:** Aggregates raw frame rows into a `LapSummary` (from `shared/models.py`). Corner segmentation uses speed minima with smoothing. See SPEC.md 7.3.
**Files:** CREATE `client/recorder/summarizer.py`
**Steps:**
1. Implement `summarize_lap(frames: list[dict], session_id: str, lap_number: int, circuit: str, car_model: str) -> LapSummary` — extracts `sector_times_ms`, `fuel_start/end/used`, `tyre_core_temp_avg`, `tyre_pressure_avg`, `tyre_wear_delta`, `abs_total_frames`, `tc_total_frames`, `lockup_events`, environment fields from frames
2. Implement `segment_corners(frames: list[dict], threshold_kmh=180, min_sep_m=50) -> list[CornerSummary]` — smooth speed trace (rolling mean window=5), find local minima below threshold, merge closer than `min_sep_m`, compute per-corner `entry/min/exit speed`, `brake_point_distance`, `brake_duration`, `max_brake`, `throttle_application_distance`, `lockup_detected`
3. Validate output against `LapSummary` schema — `LapSummary.model_validate(result)` must pass
**Acceptance:**
- [ ] `summarize_lap` returns a valid `LapSummary` from a list of frame dicts
- [ ] Corner count is reasonable for known tracks (e.g., Spa ~19 corners)

### T2.6 — Backend Uploader Thread
Status: PENDING
**Depends on:** T2.4, T2.5
**Context:** Watches SQLite `laps` table for `uploaded=0`. POSTs each pending `summary_json` to `POST /laps`. Reads config from `client/config.toml` (`[backend]` section). Backend already has `POST /laps` and `POST /sessions` endpoints.
**Files:** CREATE `client/sync/uploader.py`, MODIFY `client/config.toml`
**Steps:**
1. `UploaderThread` polls SQLite every 5s for `uploaded=0` laps, deserializes `summary_json` as `LapSummary`, POSTs to `{backend_url}/laps` with `X-API-Key` header via `httpx.post(timeout=15.0)`
2. On HTTP 200/201: set `uploaded=1`. On failure: log warning, keep `uploaded=0`, retry next cycle
3. Ensure `POST /sessions` is called once when a new `session_id` appears (creates parent session row on backend)
**Acceptance:**
- [ ] Pending laps uploaded to backend and marked `uploaded=1`
- [ ] Failed uploads retried without data loss
- [ ] Parent session created on backend before first lap upload

### T2.7 — Brake & Throttle Graph Widget
Status: PENDING
**Depends on:** T2.3
**Context:** PyQt6 widget using `pyqtgraph` to plot `brake` (0–1) and `throttle` (0–1) vs distance (m) for a selected lap. Frames come from SQLite `frames` table filtered by `(session_id, lap_number)`.
**Files:** CREATE `client/overlay/widgets/inputs_graph.py`
**Steps:**
1. Create `InputsGraphWidget(QWidget)` with a `pyqtgraph.PlotWidget`. Plot two curves: brake (red, fill to zero) and throttle (green, fill to zero) vs `distance_m`
2. Add `set_lap(session_id: str, lap_number: int)` method that queries SQLite `frames` for `brake`, `throttle`, `distance_m`, updates plot
3. Add a speed curve (blue, secondary y-axis) for context
**Acceptance:**
- [ ] Graph renders brake/throttle traces for a given lap
- [ ] Axes labeled (distance m, input 0–1, speed km/h)

### T2.8 — Steering Angle Overlay on Inputs Graph
Status: PENDING
**Depends on:** T2.7
**Context:** Extends `InputsGraphWidget` to overlay `steer` (-1 to +1) on the same distance axis. Left/right steering shown as positive/negative.
**Files:** MODIFY `client/overlay/widgets/inputs_graph.py`
**Steps:**
1. Add a third curve for `steer` (yellow) scaled to fit the 0–1 range (map -1..+1 to 0..0.5 range or use a dedicated y-axis)
2. Add a checkbox toggle to show/hide the steering trace
3. Add legend with color indicators for all traces
**Acceptance:**
- [ ] Steering angle visible alongside brake/throttle
- [ ] Toggle works, legend present

### T2.9 — Draggable Floating Graph Window
Status: PENDING
**Depends on:** T2.7
**Context:** The graph widget must be a frameless, semi-transparent window that the user can drag anywhere on a multi-monitor setup. `Qt.WindowType.FramelessWindowHint` + custom drag handling.
**Files:** CREATE `client/overlay/widgets/floating_graph_window.py`
**Steps:**
1. Create `FloatingGraphWindow(QWidget)` — frameless (`Qt.WindowType.FramelessWindowHint`), always-on-top (`Qt.WindowType.WindowStaysOnTopHint`), semi-transparent background (`setWindowOpacity(0.85)`)
2. Implement drag-to-move via `mousePressEvent` / `mouseMoveEvent` tracking offset; also respond to `QKeyEvent` for position snapping
3. Embed `InputsGraphWidget` inside. Add a collapse/expand button and a close button in a tiny title bar
**Acceptance:**
- [ ] Window is frameless and draggable across monitors
- [ ] Opacity configurable, collapse/expand works

### T2.10 — Backend Data Viewer UI
Status: PENDING
**Depends on:** T2.6 (backend has data to view)
**Context:** PyQt6 tab widget that fetches sessions/laps from backend via `GET /sessions`, `GET /sessions/{id}/laps`. Displays a session list on the left, lap details on the right. Reuses config from `client/config.toml`.
**Files:** CREATE `client/overlay/data_viewer.py`
**Steps:**
1. Left panel: `QListWidget` showing sessions (circuit, car, date). Fetch via `GET /sessions` (add a simple list endpoint to backend if missing: `GET /sessions` returns all sessions)
2. Right panel: `QTableWidget` showing laps for selected session (lap number, time, valid, sectors). Fetch via `GET /sessions/{id}/laps`
3. Double-click a lap to open it in the `InputsGraphWidget` (T2.7) — fetches frame data from local SQLite
**Acceptance:**
- [ ] Sessions listed with circuit/car/date
- [ ] Laps load on session selection with times and validity
- [ ] Double-clicking a lap opens the graph widget with that lap's data

---

## Planning References

- **SPEC.md** — Full feature specification
- **CLAUDE.md** — Architecture rules and development commands
- **Branch naming**: `sprint-N-<kebab-name>`
- **PR workflow**: All sprint tasks → feature branch → PR (main) → Codex review → QA → merge
