# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

An AI-powered coaching overlay for Assetto Corsa Competizione (ACC). Two independently deployable components:

- **Overlay Client** (`client/`) — Windows desktop app (Python/PyQt6) that reads live telemetry from ACC via shared memory, records laps to SQLite, plays real-time audio cues, and uploads lap summaries to the backend.
- **Backend API** (`backend/`) — Dockerized FastAPI server that stores laps in PostgreSQL and generates LLM-powered coaching analysis via the Anthropic API.
- **Shared models** (`shared/`) — Pydantic v2 schemas imported by both components. This is the single source of truth for all data shapes — never redefine them in client or backend code.

The full specification is in `SPEC.md`. Read it before making architectural decisions.

---

## Development Commands

### Backend

```bash
# Start backend + PostgreSQL
docker compose up -d

# View API logs
docker compose logs -f api

# Run Alembic migrations manually
docker compose exec api alembic upgrade head

# Run backend locally (requires DATABASE_URL in environment)
cd backend
uvicorn main:app --reload
```

### Client

```bash
# Run the overlay client
cd client
python main.py

# Package to .exe
pyinstaller --onefile --windowed client/main.py
```

### Linting & Type Checking

```bash
ruff check .
mypy .
```

---

## Architecture

### Data Flow

1. ACC writes telemetry to Windows shared memory (`acpmf_physics`, `acpmf_graphics`, `acpmf_static`)
2. Client pollers read these at 60 Hz / 25 Hz and push frames to `queue.Queue`s
3. `RecorderThread` consumes queues, detects lap boundaries, writes frames to SQLite
4. At lap end, `summarizer.py` aggregates raw frames into a `LapSummary`
5. `UploaderThread` POSTs pending `LapSummary` objects to the backend
6. Backend stores laps in PostgreSQL; on analysis request, `diff.py` builds a `DeltaReport` comparing driver vs reference lap
7. `llm.py` serializes the `DeltaReport` as compact JSON and sends it to `claude-opus-4-6` for analysis
8. `AnalysisResult` is stored and returned to the client for display in the overlay

### Client Thread Model

| Thread | Responsibility |
|---|---|
| `MainThread` | PyQt6 event loop |
| `PhysicsPollerThread` | Reads `acpmf_physics` at ~60 Hz |
| `GraphicsPollerThread` | Reads `acpmf_graphics` at ~25 Hz |
| `RecorderThread` | Lap boundary detection, SQLite writes |
| `AudioThread` | Evaluates cue conditions, fires sounds |
| `UploaderThread` | Watches SQLite for `uploaded=0`, POSTs to backend |

All inter-thread communication uses `queue.Queue`. No shared mutable state between threads.

### Corner Segmentation

Corners are detected from speed minima: smooth the speed trace, find local minima below `corner_speed_threshold_kmh` (default 180), merge minima closer than `min_corner_separation_m` (default 50 m). The braking zone is frames before apex where `brake > 0.05`; exit zone ends when `throttle > 0.8` sustained.

### LLM Token Optimization

The `DeltaReport` in `backend/services/diff.py` is the only artifact sent to the LLM — never raw frames or full `LapSummary` arrays. Key design choices:
- Abbreviated field keys (`bp_d` not `brake_point_delta_m`)
- Fixed numeric precision (time deltas as int ms, speeds to 1 dp, inputs to 2 dp)
- Top 8 corners by `|t_d|` only, with a `TailAggregate` for the rest
- Compact JSON serialization (no whitespace)
- Legend defined once in the system prompt (`backend/prompts/racing_engineer.txt`), not repeated per request
- Typical payload: 400–700 input tokens per lap analysis

LLM call settings: model `claude-opus-4-6`, max_tokens 1500, temperature 0.3, response must be valid JSON matching `AnalysisResult`.

### Reference Lap Ingestion

Reference laps come from ACC replay files. The client runs the same shared-memory poller with `status == ACC_REPLAY` tolerated, records frames, and runs them through the same `summarizer.py`. This means reference and driver laps are structurally identical — no special-casing in the diff engine.

---

## Key Implementation Rules

1. **Never write to ACC shared memory.** Read-only access only.
2. **Never pass raw frame arrays to the LLM.** Always summarize via `summarizer.py` then diff via `diff.py`.
3. **All inter-thread communication uses `queue.Queue`.** No shared mutable state between threads.
4. **`shared/models.py` is the source of truth.** Do not redefine schemas in client or backend.
5. **Audio files must be pre-loaded at startup** via `pygame.mixer.Sound()`. Never load from disk on a trigger.
6. **Guard every shared memory read.** If the game is not running, poll silently and retry — never crash.
7. **SQLite uploads are idempotent.** Set `uploaded=1` only on confirmed HTTP 200/201. Retry on failure.
8. **All backend DB access is async.** Use `async with session:` throughout. No sync SQLAlchemy calls.
9. **Migrations via Alembic only.** Never use `Base.metadata.create_all()`.

---

## Environment Configuration

Backend uses `.env` (copy from `.env.example`):
- `DATABASE_URL` — async PostgreSQL URL (`postgresql+asyncpg://...`)
- `ANTHROPIC_API_KEY`
- `API_KEY` — used as `X-API-Key` header for all API requests
- `DB_PASSWORD`

Client uses `client/config.toml` (human-editable TOML, parsed with stdlib `tomllib`).
