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

### Sprint 2 — Client Telemetry & Visualization ✓
Branch: `sprint-2-client-telemetry` → Merged to `main`
Status: DONE (2026-04-10)
PR: https://github.com/StefanGrozde/acc-coach/pull/2

**Summary**: Built complete client-side telemetry pipeline for ACC, including shared memory pollers (physics ~60Hz, graphics ~25Hz), SQLite frame storage, lap boundary detection, real-time and historical input graphing, and a draggable overlay UI for live data visualization.

**Tasks Completed**:
- T2.1 — ACC shared memory reader (`client/poller/shared_memory.py`, `client/poller/structs.py`) with `SPageFilePhysics`, `SPageFileGraphic`, `SPageFileStatic` structs
- T2.2 — Poller threads (`client/poller/physics_poller.py`, `client/poller/graphics_poller.py`) pushing frames to `queue.Queue` at target Hz rates
- T2.3 — SQLite schema (`client/store/database.py`) with `frames`, `laps`, `reference_laps` tables and indexes
- T2.4 — Lap recorder thread (`client/recorder/lap_recorder.py`) with session/lap tracking and boundary detection
- T2.5 — Placeholder lap summarization (full corner segmentation deferred to future sprint)
- T2.6 — Backend uploader thread (`client/sync/uploader.py`) with httpx/fallback HTTP client, session creation, and retry logic (uploads disabled pending proper summarization)
- T2.7 — Inputs graph widget (`client/overlay/widgets/inputs_graph.py`) with brake/throttle/steering/speed curves, time-based x-axis
- T2.8 — Steering overlay with toggle checkbox and legend
- T2.9 — Draggable floating graph window (`client/overlay/widgets/floating_graph_window.py`) with frameless always-on-top overlay, keyboard positioning, collapse/expand
- T2.10 — Backend data viewer UI (`client/overlay/data_viewer.py`) with local SQLite laps browsing, remote session fetching, lap table with double-click to open graph

**Bonus Features Added**:
- Live real-time inputs graph (`client/overlay/widgets/live_inputs_graph.py`, `client/overlay/widgets/floating_live_window.py`) with 30-second rolling window showing brake/throttle/steering/speed at ~30Hz
- "Load Local Laps" button for offline SQLite data access (no backend required)
- Frameless window styling with transparency and rounded corners
- Multi-monitor support with keyboard positioning (arrow keys, Ctrl/Cmd combos for snapping)

**Key Files Created**:
- `client/poller/shared_memory.py`, `client/poller/structs.py`
- `client/poller/physics_poller.py`, `client/poller/graphics_poller.py`
- `client/store/database.py`
- `client/recorder/lap_recorder.py`
- `client/sync/uploader.py`
- `client/overlay/widgets/inputs_graph.py`, `client/overlay/widgets/floating_graph_window.py`
- `client/overlay/widgets/live_inputs_graph.py`, `client/overlay/widgets/floating_live_window.py`
- `client/overlay/data_viewer.py`
- `client/main.py` (updated to wire all Sprint 2 components)

**Bugs Fixed (Post-Review)**:
- Security: Added `.gitignore`, removed `client/config.toml` with API credentials, created `config.toml.example`
- Recorder shutdown: Added `app.aboutToQuit` handler to properly `stop()`/`join()` daemon threads
- Live graph speed curve: Fixed missing speed data updates in rolling plot (added `_speed_values` deque and update logic)
- Import paths: Fixed absolute imports → relative imports for client directory execution
- Added project root to `sys.path` for shared package access

**Known Limitations**:
- Sector times show "-" (requires sector split detection logic)
- Placeholder summaries used instead of full `LapSummary` objects (corner segmentation, sector times, tyre data aggregation not implemented)
- Backend uploads disabled (pending proper lap summarization)

---

### Sprint 3 — Lap Summarization & Upload Pipeline
Branch: `sprint-3-client-summarization`
Status: DONE (2026-04-10)

**Summary**: Fix the three known limitations from Sprint 2 by implementing real sector split detection, full corner segmentation, and proper LapSummary generation, then re-enable backend uploads.

**Tasks**:

#### T3.1 — Capture sector split data in graphics poller
Status: DONE (2026-04-10)

Modify `client/poller/graphics_poller.py` to include `current_sector_index` and `last_sector_time` in the emitted frame dict. These fields (`currentSectorIndex`, `lastSectorTime`) already exist in `SPageFileGraphic` but are not being read.

**Files**: MODIFY `client/poller/graphics_poller.py`
- Add `"current_sector_index": int(graphics.currentSectorIndex)` to `_build_frame()`
- Add `"last_sector_time": int(graphics.lastSectorTime)` to `_build_frame()`

**Acceptance**: Graphics frames in the queue contain `current_sector_index` (0-based sector number) and `last_sector_time` (ms). When the summarizer receives these, `_derive_sector_times()` uses real sector boundaries instead of distance-based splitting.

---

#### T3.2 — Read sectorCount from static data
Status: DONE (2026-04-10)

The recorder reads `track` and `carModel` from `SPageFileStatic` in `_read_static_metadata()`. Extend it to also read `sectorCount` so the summarizer knows how many sectors the track has (most ACC tracks have 3, but some differ).

**Files**: MODIFY `client/recorder/lap_recorder.py`
- Add `self._sector_count: int = 3` field
- In `_read_static_metadata()`, read `static.sectorCount` and store it
- Pass `sector_count` through to the summarizer call (T3.3)

**Acceptance**: `sectorCount` from ACC static memory is available for sector time derivation.

---

#### T3.3 — Wire summarize_lap() into lap finalization
Status: DONE (2026-04-10)
Depends on: T3.1, T3.2, T3.4

Replace the placeholder summary with a real `LapSummary` by calling `summarize_lap()` from `summarizer.py` inside `_finalize_current_lap()`.

**Files**: MODIFY `client/recorder/lap_recorder.py`
- Import `summarize_lap` from `recorder.summarizer`
- In `_finalize_current_lap()`, call `summarize_lap(frames, session_id, lap_number, circuit, car_model)` instead of `_placeholder_summary_json()`
- Serialize the resulting `LapSummary` with `.model_dump_json()` for storage in SQLite
- Remove `_placeholder_summary_json()` method once the real summarizer is wired

**Acceptance**: Every completed lap produces a valid `LapSummary` with real `CornerSummary` objects, sector times, tyre data, fuel data, and intervention counts. The `summary_json` column in SQLite contains valid `LapSummary` JSON that passes `LapSummary.model_validate_json()`.

---

#### T3.4 — Persist full telemetry fields for summarization
Status: DONE (2026-04-10)

The physics poller already emits tyre temp, pressure, wheel slip, and fuel. However, the recorder's `_build_frame_payload()` and the database `insert_frame()` must ensure these fields survive the round-trip from queue to SQLite to summarizer. Verify the data pipeline and fill any gaps.

**Files**: MODIFY `client/recorder/lap_recorder.py`, `client/store/database.py`, `client/recorder/summarizer.py`, `client/poller/physics_poller.py`
- Confirm that `tyre_temp`, `tyre_pressure`, `wheel_slip`, `fuel`, `tyreWear`, `tyreCoreTemperature` from physics frames are preserved in `raw_json` via `insert_frame()`
- If the physics poller is missing `tyreWear` or `tyreCoreTemperature`, add them to `_build_frame()` in `client/poller/physics_poller.py`
- Verify `_normalize_frame()` in `summarizer.py` can extract these fields from the stored `raw_json`

**Acceptance**: A lap's frames stored in SQLite contain all fields needed by `summarize_lap()` to populate every field of `LapSummary` (tyre temps, pressures, wear, fuel, wheel slip, ABS, TC, environment).

---

#### T3.5 — Re-enable and verify backend uploads
Status: DONE (2026-04-10)
Depends on: T3.3

Once T3.3 produces valid `LapSummary` JSON, the uploader in `client/sync/uploader.py` should successfully parse it via `_load_lap_summary()` and POST it to the backend. Test the full pipeline end-to-end.

**Files**: MODIFY `client/sync/uploader.py`
- Verify that `upload_enabled = true` in `config.toml.example` is respected
- Confirm `_parse_pending_lap()` successfully validates the new `LapSummary` JSON
- Add a log line at INFO level when a lap is successfully uploaded
- If `upload_enabled` is `false` in config, the uploader should still start but log that it is disabled (already works this way)

**Acceptance**: With `upload_enabled = true` in config and a running backend, completed laps are uploaded within the poll interval. The `uploaded` column flips to `1`. If the backend is unreachable, laps remain `uploaded = 0` and are retried.

---

#### T3.6 — Add manual recording toggle button
Status: DONE (2026-04-10)

Add a "Start/Stop Recording" button to the UI that allows the user to control when laps are recorded. When disabled, the pollers still run but the recorder skips lap finalization. When enabled, the next lap completion triggers recording.

**Files**: MODIFY `client/recorder/lap_recorder.py`, `client/overlay/data_viewer.py`
- Add `self._recording_enabled: bool = False` flag to `RecorderThread`
- Add `start_recording()` and `stop_recording()` methods to `RecorderThread` that toggle the flag
- Modify `_finalize_current_lap()` to return early if `not self._recording_enabled`
- Add a "Start Recording" button to `BackendDataViewer` UI (near "Load Local Laps" button)
- Button should toggle between "Start Recording" and "Stop Recording" with visual indicator (red/green or icon)
- When "Start Recording" is clicked, call `recorder.start_recording()`
- When "Stop Recording" is clicked, call `recorder.stop_recording()`
- Pass recorder reference to `BackendDataViewer` in `main.py`

**Acceptance**: User can click "Start Recording" and the next lap completed is saved to SQLite. Click "Stop Recording" and subsequent laps are ignored. Button state clearly shows whether recording is active. Pollers and graphics still work when recording is disabled.

---

**Suggested Next Priorities (post-Sprint 3)**:
1. Audio cue system — Real-time brake point warnings, lockup detection alerts, flag calls, fuel/pit window notifications
2. LLM analysis service — Build DeltaReport from driver vs reference lap, send to claude-opus-4-6 for structured coaching feedback
3. Reference lap management — Upload/download reference laps via API, replay ingestion mode

---

## Planning References

- **SPEC.md** — Full feature specification
- **CLAUDE.md** — Architecture rules and development commands
- **Branch naming**: `sprint-N-<kebab-name>`
- **PR workflow**: All sprint tasks → feature branch → PR (main) → Codex review → QA → merge
