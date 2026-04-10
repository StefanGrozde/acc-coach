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

## Planning References

- **SPEC.md** — Full feature specification
- **CLAUDE.md** — Architecture rules and development commands
- **Branch naming**: `sprint-N-<kebab-name>`
- **PR workflow**: All sprint tasks → feature branch → PR (main) → Codex review → QA → merge
