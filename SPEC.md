# ACC Coaching Overlay — Project Specification

> This document is the authoritative reference for all coding agents working on this project.
> Read it fully before writing any code. Do not deviate from the architecture described here
> without updating this document first.

---

## 1. Project Overview

A **Windows desktop overlay** for Assetto Corsa Competizione that:

- Reads live telemetry via the ACC Shared Memory SDK
- Records and stores lap telemetry to a local database
- Delivers real-time audio cues (brake points, lockups, flags, etc.)
- Sends post-session telemetry summaries to a backend for LLM-powered coaching analysis
- Displays coaching feedback in a transparent on-screen overlay and/or a web dashboard

The system is split into two independently deployable components:

| Component | Runtime | Location |
|---|---|---|
| **Overlay Client** | Windows desktop app (Python) | Driver's gaming PC |
| **Backend API** | Docker container (Python/FastAPI) | Remote server |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DRIVER'S PC (Windows)                │
│                                                         │
│  ┌──────────────┐    Shared Memory     ┌─────────────┐ │
│  │     ACC      │ ──────────────────►  │   Poller    │ │
│  │   (Game)     │  acpmf_physics        │   Thread    │ │
│  └──────────────┘  acpmf_graphics       └──────┬──────┘ │
│                    acpmf_static                │        │
│                                         ┌──────▼──────┐ │
│                                         │  Lap        │ │
│                                         │  Recorder   │ │
│                                         └──────┬──────┘ │
│                                                │        │
│                              ┌─────────────────┼──────┐ │
│                              │                 │      │ │
│                       ┌──────▼──────┐   ┌──────▼────┐ │ │
│                       │   SQLite    │   │  Audio    │ │ │
│                       │    Store    │   │  Engine   │ │ │
│                       └──────┬──────┘   └───────────┘ │ │
│                              │                        │ │
│                       ┌──────▼──────┐                 │ │
│                       │   Overlay   │                 │ │
│                       │    UI       │                 │ │
│                       └──────┬──────┘                 │ │
│                              │  HTTP (REST)           │ │
└──────────────────────────────┼─────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   REMOTE SERVER     │
                    │  ┌───────────────┐  │
                    │  │  FastAPI App  │  │
                    │  │  (Docker)     │  │
                    │  └──────┬────────┘  │
                    │         │           │
                    │  ┌──────▼────────┐  │
                    │  │  PostgreSQL   │  │
                    │  │  (Docker)     │  │
                    │  └──────┬────────┘  │
                    │         │           │
                    │  ┌──────▼────────┐  │
                    │  │  Anthropic    │  │
                    │  │  Claude API   │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

---

## 3. Tech Stack

### 3.1 Overlay Client (Windows)

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Rapid dev, ctypes for shared memory, rich ecosystem |
| Shared memory | `ctypes` + `mmap` via `win32api` (`pywin32`) | Direct Windows API access |
| UI framework | `PyQt6` | Transparent frameless windows, good performance |
| Audio | `pygame.mixer` | Low-latency, supports simultaneous sounds, easy preloading |
| Local database | `SQLite` via `sqlite3` stdlib | Zero-config, sufficient for single-user lap storage |
| HTTP client | `httpx` (async) | Async-native, clean API |
| Data validation | `pydantic v2` | Shared schema models with backend |
| Packaging | `PyInstaller` | Single `.exe` for distribution |
| Config | `TOML` via `tomllib` (stdlib 3.11) | Human-editable settings file |

### 3.2 Backend (Docker / Server)

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Shared pydantic models, consistent codebase |
| Framework | `FastAPI` | Async, OpenAPI docs out of the box, pydantic native |
| ASGI server | `uvicorn` with `gunicorn` | Production-grade process management |
| Database | `PostgreSQL 15` | Relational, good JSON support for telemetry blobs |
| ORM | `SQLAlchemy 2.0` (async) | Async session support, clean migrations |
| Migrations | `Alembic` | Schema versioning |
| LLM | `anthropic` Python SDK | `claude-opus-4-6` for analysis |
| Prompt cache | Anthropic prompt caching (system prompt + legend) | Cuts repeat-batch cost ~90% |
| Containerisation | `Docker` + `Docker Compose` | Isolated deployment |
| Auth | API key header (`X-API-Key`) | Simple, sufficient for single-user / private server |
| Logging | `structlog` | JSON structured logs for server-side debugging |

### 3.3 Shared

| Concern | Choice |
|---|---|
| Schema definitions | `pydantic v2` models in a `shared/` package imported by both client and backend |
| Environment config | `.env` files loaded via `python-dotenv` |
| Formatting | `ruff` |
| Type checking | `mypy` |

---

## 4. Repository Structure

```
acc-coaching/
├── client/                         # Windows overlay client
│   ├── main.py                     # Entry point
│   ├── config.toml                 # User-editable settings
│   ├── poller/
│   │   ├── __init__.py
│   │   ├── shared_memory.py        # ctypes structs + memory map reader
│   │   └── structs.py              # SPageFilePhysics, Graphic, Static as ctypes Structures
│   ├── recorder/
│   │   ├── __init__.py
│   │   ├── lap_recorder.py         # Detects lap boundaries, writes frames to SQLite
│   │   └── summarizer.py           # Aggregates raw frames into LapSummary
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── engine.py               # Sound cue dispatcher with debounce/cooldown
│   │   ├── cues.py                 # Cue definitions and trigger conditions
│   │   └── sounds/                 # .wav files (brake, lockup, flag, pit, etc.)
│   ├── overlay/
│   │   ├── __init__.py
│   │   ├── window.py               # PyQt6 transparent overlay window
│   │   └── widgets/                # Individual HUD widgets
│   ├── store/
│   │   ├── __init__.py
│   │   └── database.py             # SQLite schema + queries
│   └── sync/
│       ├── __init__.py
│       └── uploader.py             # Sends LapSummary to backend API
│
├── backend/                        # FastAPI backend
│   ├── main.py                     # FastAPI app + router registration
│   ├── routers/
│   │   ├── laps.py                 # POST /laps, GET /laps, GET /laps/{id}
│   │   ├── sessions.py             # POST /sessions, GET /sessions/{id}
│   │   └── analysis.py             # POST /analysis/session/{id}
│   ├── services/
│   │   ├── llm.py                  # LLM prompt builder + Anthropic API calls
│   │   └── diff.py                 # Reference lap diff engine
│   ├── models/
│   │   ├── orm.py                  # SQLAlchemy ORM models
│   │   └── schemas.py              # Pydantic request/response schemas
│   ├── db/
│   │   ├── session.py              # Async SQLAlchemy engine + session factory
│   │   └── migrations/             # Alembic migrations
│   │       └── versions/
│   ├── prompts/
│   │   └── racing_engineer.txt     # System prompt for LLM analysis
│   ├── Dockerfile
│   └── requirements.txt
│
├── shared/                         # Shared pydantic models (installed as local package)
│   ├── __init__.py
│   └── models.py                   # LapSummary, CornerSummary, SessionSummary, etc.
│
├── docker-compose.yml
├── .env.example
└── SPEC.md
```

---

## 5. Data Schema

### 5.1 Core Pydantic Models (`shared/models.py`)

These are the canonical data shapes used by both client and backend.

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import IntEnum

class WheelData(BaseModel):
    """Consistent FL, FR, RL, RR ordering for all wheel arrays."""
    fl: float
    fr: float
    rl: float
    rr: float

class CornerSummary(BaseModel):
    corner_index: int               # 0-based index from distanceTraveled segmentation
    corner_name: Optional[str]      # Optional human label ("T1", "Eau Rouge", etc.)
    entry_speed_kmh: float
    min_speed_kmh: float            # Apex speed
    exit_speed_kmh: float
    brake_point_distance_m: float   # distanceTraveled when brake > 0.05
    brake_duration_ms: int
    max_brake_input: float          # Peak brake value (0.0–1.0)
    abs_intervention_peak: float    # Peak abs field value during braking
    abs_intervention_count: int     # Frames where abs > 0.0
    throttle_application_distance_m: float
    tc_intervention_peak: float
    tc_intervention_count: int
    max_rear_wheel_slip: float
    lockup_detected: bool           # wheelSlip any wheel > LOCKUP_THRESHOLD while braking

class LapSummary(BaseModel):
    session_id: str                 # UUID, assigned by client at session start
    lap_number: int
    lap_time_ms: int
    is_valid: bool                  # Based on ACC penalty/cut detection
    circuit: str                    # From SPageFileStatic.track
    car_model: str                  # From SPageFileStatic.carModel
    recorded_at: datetime

    sector_times_ms: list[int]      # Length = sectorCount from Static

    corners: list[CornerSummary]

    # Tyre summary (averages over the lap)
    tyre_core_temp_avg: WheelData
    tyre_pressure_avg: WheelData
    tyre_wear_delta: WheelData      # Wear at lap end minus wear at lap start

    # Fuel
    fuel_start_litres: float
    fuel_end_litres: float
    fuel_used_litres: float

    # Aggregate driver aid interventions
    abs_total_frames: int
    tc_total_frames: int
    lockup_events: int

    # Environment (snapshot from mid-lap)
    track_grip_status: str          # ACC_TRACK_GRIP_STATUS string
    rain_intensity: str             # ACC_RAIN_INTENSITY string
    air_temp_c: Optional[float]
    track_temp_c: Optional[float]

class SessionSummary(BaseModel):
    session_id: str
    session_type: str               # ACC_SESSION_TYPE string
    circuit: str
    car_model: str
    started_at: datetime
    laps: list[LapSummary]

class AnalysisRequest(BaseModel):
    session_id: str
    reference_lap_id: Optional[str] = None   # If None, backend uses best lap in session
    focus_areas: Optional[list[str]] = None  # e.g. ["braking", "consistency"]

class CornerFeedback(BaseModel):
    corner_index: int
    corner_name: Optional[str]
    time_loss_estimate_ms: Optional[int]
    issues: list[str]
    recommendations: list[str]

class AnalysisResult(BaseModel):
    session_id: str
    generated_at: datetime
    overall_summary: str
    top_weaknesses: list[str]       # Ordered by estimated time impact
    corner_feedback: list[CornerFeedback]
    positive_observations: list[str]
    focus_for_next_stint: str
    raw_llm_response: str           # Stored for debugging
```

---

### 5.2 SQLite Schema (Client-side)

```sql
-- One row per physics tick sampled at ~60Hz during a lap
CREATE TABLE frames (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    lap_number  INTEGER NOT NULL,
    packet_id   INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,  -- ms since session start

    -- Physics fields (subset — full frame stored as JSON blob)
    distance_m      REAL,
    speed_kmh       REAL,
    brake           REAL,
    throttle        REAL,
    gear            INTEGER,
    rpms            INTEGER,
    steer_angle     REAL,
    abs_active      REAL,
    tc_active       REAL,

    -- JSON blob for full frame (allows schema evolution)
    raw_json    TEXT
);

CREATE INDEX idx_frames_session_lap ON frames(session_id, lap_number);

-- Aggregated lap summaries (uploaded to backend)
CREATE TABLE laps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    lap_number  INTEGER NOT NULL,
    lap_time_ms INTEGER,
    is_valid    INTEGER,
    circuit     TEXT,
    car_model   TEXT,
    recorded_at TEXT,
    summary_json TEXT,              -- Serialised LapSummary JSON
    uploaded    INTEGER DEFAULT 0   -- 0 = pending upload, 1 = uploaded
);

-- Reference laps sourced from community or self-recorded
CREATE TABLE reference_laps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    circuit     TEXT NOT NULL,
    car_model   TEXT NOT NULL,
    lap_time_ms INTEGER,
    source      TEXT,               -- "self", "community", "imported"
    summary_json TEXT,
    added_at    TEXT
);
```

---

### 5.3 PostgreSQL Schema (Backend)

```sql
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT UNIQUE NOT NULL,   -- Client-generated UUID
    session_type TEXT,
    circuit     TEXT,
    car_model   TEXT,
    started_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE laps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    lap_number  INTEGER NOT NULL,
    lap_time_ms INTEGER,
    is_valid    BOOLEAN,
    circuit     TEXT,
    car_model   TEXT,
    recorded_at TIMESTAMPTZ,
    summary     JSONB NOT NULL,         -- Full LapSummary as JSONB
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(session_id, lap_number)
);

CREATE TABLE analyses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    generated_at TIMESTAMPTZ DEFAULT now(),
    result      JSONB NOT NULL,         -- Full AnalysisResult as JSONB
    model_used  TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER
);

CREATE TABLE reference_laps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circuit     TEXT NOT NULL,
    car_model   TEXT NOT NULL,
    lap_time_ms INTEGER,
    source      TEXT,
    summary     JSONB NOT NULL,
    added_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_laps_session ON laps(session_id);
CREATE INDEX idx_laps_circuit_car ON laps(circuit, car_model);
CREATE INDEX idx_analyses_session ON analyses(session_id);
```

---

## 6. API Specification

Base URL: `https://your-server.com/api/v1`

All requests require header: `X-API-Key: <key>`

### Endpoints

```
POST   /sessions
       Body: { session_id, session_type, circuit, car_model, started_at }
       Returns: Session object

POST   /laps
       Body: LapSummary (see shared/models.py)
       Returns: { id, session_id, lap_number }
       Note: Client calls this at the end of each valid lap

GET    /sessions/{session_id}/laps
       Returns: list[LapSummary]

POST   /analysis/session/{session_id}
       Body: AnalysisRequest
       Returns: AnalysisResult
       Note: Triggers LLM analysis. Client calls after N laps or end of session.
       This is a synchronous call — keep max_tokens reasonable (~1500).

GET    /analysis/session/{session_id}/latest
       Returns: AnalysisResult | 404

GET    /reference-laps?circuit={circuit}&car_model={car_model}
       Returns: list[ReferenceLap]

POST   /reference-laps
       Body: LapSummary + source field
       Returns: ReferenceLap
```

---

## 7. Client Poller & Recorder Logic

### 7.1 Thread Architecture

```
MainThread          — PyQt6 UI event loop
PhysicsPollerThread — Reads acpmf_physics at ~60Hz, pushes to queue
GraphicsPollerThread— Reads acpmf_graphics at ~25Hz, pushes to queue
RecorderThread      — Consumes queues, detects laps, writes SQLite
AudioThread         — Evaluates cue conditions, fires sounds
UploaderThread      — Watches SQLite for uploaded=0 rows, POSTs to backend
```

### 7.2 Lap Boundary Detection

```python
# A new lap begins when:
# - numberOfLaps increments in acpmf_graphics
# - OR distanceTraveled resets close to 0 while it was > threshold
# - AND status == ACC_LIVE (ignore ACC_REPLAY / ACC_PAUSE)

# A lap is marked INVALID if:
# - penalty field is non-None at any point during the lap
# - The lap_time is < plausible minimum for the circuit (configurable)
```

### 7.3 Corner Segmentation

Corners are identified from recorded frames using speed minima:

```python
# Algorithm:
# 1. Smooth speedKmh trace with a rolling window
# 2. Find local minima below CORNER_SPEED_THRESHOLD (configurable, e.g. 160 km/h)
# 3. Each minimum defines a corner apex
# 4. Braking zone = frames before apex where brake > 0.05
# 5. Exit zone = frames after apex until throttle > 0.8 sustained
# 6. Merge minima closer than MIN_CORNER_SEPARATION_M (e.g. 50m) as chicanes
```

---

## 8. Audio Cue System

### 8.1 Cue Definitions

Each cue has:
- **Trigger condition** — evaluated every physics frame
- **Cooldown** — minimum ms before the same cue fires again
- **Priority** — higher priority cues interrupt lower priority ones
- **Sound file** — pre-loaded `.wav`

```python
CUES = [
    Cue(
        name="brake_point",
        priority=10,
        cooldown_ms=8000,
        sound="brake_now.wav",
        # Trigger: approaching reference brake point, speed-adjusted
    ),
    Cue(
        name="lockup",
        priority=9,
        cooldown_ms=2000,
        sound="lockup.wav",
        # Trigger: any wheelSlip > 0.3 while brake > 0.6
    ),
    Cue(
        name="tc_intervention",
        priority=5,
        cooldown_ms=3000,
        sound="tc_warning.wav",
        # Trigger: tc > 0.5 sustained for > 3 frames
    ),
    Cue(
        name="blue_flag",
        priority=8,
        cooldown_ms=10000,
        sound="blue_flag.wav",
        # Trigger: flag == ACC_BLUE_FLAG
    ),
    Cue(
        name="pit_window_open",
        priority=7,
        cooldown_ms=999999,  # Fire once
        sound="pit_window_open.wav",
        # Trigger: sessionTimeLeft crosses pitWindowStart
    ),
    Cue(
        name="low_fuel",
        priority=6,
        cooldown_ms=30000,
        sound="low_fuel.wav",
        # Trigger: fuel < LOW_FUEL_THRESHOLD_LITRES (config)
    ),
]
```

### 8.2 Brake Point Trigger Logic

```python
def should_trigger_brake_cue(current: PhysicsFrame, ref: ReferenceLap) -> bool:
    ref_brake_distance = ref.get_next_brake_point(current.distance_m)
    if ref_brake_distance is None:
        return False

    distance_to_brake = ref_brake_distance - current.distance_m
    speed_ratio = current.speed_kmh / ref.speed_at(ref_brake_distance)
    adjusted_trigger_distance = BASE_TRIGGER_DISTANCE_M * speed_ratio

    return (
        distance_to_brake <= adjusted_trigger_distance
        and current.brake < 0.05          # Driver hasn't braked yet
        and current.speed_kmh > MIN_SPEED_FOR_CUE_KMH
    )
```

---

## 9. LLM Analysis Service

### 9.1 Prompt Construction (`backend/services/llm.py`)

```python
def build_analysis_prompt(
    session: SessionSummary,
    diff: Optional[DiffReport]
) -> str:
    """
    Never pass raw frame data to the LLM.
    Always pass pre-aggregated LapSummary + optional DiffReport.
    """
```

The system prompt lives in `backend/prompts/racing_engineer.txt` and is loaded at startup — not hardcoded in Python. This allows tuning without code changes.

### 9.2 LLM Call Contract

```python
# Model: claude-opus-4-6
# Max tokens: 1500
# Temperature: 0.3 (low — we want consistent, analytical output not creative)
# Response must be valid JSON matching AnalysisResult schema
# Use structured output / JSON mode where available
```

### 9.3 Delta Report — Token-Optimized LLM Payload (`backend/services/diff.py`)

This is the **single structured artifact** passed to the LLM. Its design is governed by
three rules:

1. **Every field must be actionable.** If the LLM cannot recommend a fix based on a field,
   it is removed. No raw frames, no per-sample arrays, no redundant absolutes alongside deltas.
2. **Short keys, numeric values, fixed precision.** Keys are abbreviated (`bp_d` not
   `brake_point_delta_m`); floats are rounded to the minimum precision that preserves
   signal (speeds to 1 dp, deltas in ms as ints, inputs to 2 dp).
3. **Corners are sorted by `|t_d|` descending and truncated to the top N (default 8).**
   The tail is summarized as an aggregate so the LLM sees the full picture without paying
   tokens for irrelevant clean corners.

The report is serialized as **compact JSON** (no whitespace, no indent) and prefixed with
a short legend that the system prompt references once. A typical 1-stint delta report
fits in **~400–700 input tokens**.

#### 9.3.1 Schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

# -------- Corner-level delta (compact keys) --------
class CornerDelta(BaseModel):
    """
    All *_d fields are driver_value - reference_value.
    Positive t_d = time LOST vs reference.
    Units encoded in the legend, not repeated per field.
    """
    i:    int                       # corner_index
    n:    Optional[str] = None      # short name ("T1") — omitted if unknown
    t_d:  int                       # estimated_time_delta_ms  (+ = lost)
    bp_d: float                     # brake_point_delta_m      (+ = braked later)
    bd_d: int                       # brake_duration_delta_ms
    mb_d: float                     # max_brake_delta          (-1..1)
    ms_d: float                     # min_speed_delta_kmh      (+ = faster apex)
    xs_d: float                     # exit_speed_delta_kmh
    th_d: float                     # throttle_application_distance_delta_m (+ = later)
    abs_d: float                    # abs_intervention_peak_delta
    tc_d:  float                    # tc_intervention_peak_delta
    slip:  float                    # max_rear_wheel_slip_delta
    lock:  bool = False             # lockup_detected this lap (reference had none)
    # Compact tag list — the LLM's main "hint" surface.
    # Values drawn from a fixed vocabulary so the LLM learns them once.
    tags: list[Literal[
        "late_brake", "early_brake", "over_brake", "under_brake",
        "early_throttle", "late_throttle", "lockup", "abs_heavy",
        "tc_heavy", "apex_slow", "apex_fast", "exit_slow", "wide_exit",
        "trail_short", "trail_long"
    ]] = Field(default_factory=list)

# -------- Lap-level aggregate --------
class LapDeltaHeader(BaseModel):
    track: str                      # circuit short code ("spa", "monza")
    car:   str                      # car model short code
    ref_t: int                      # reference lap_time_ms
    drv_t: int                      # driver lap_time_ms
    tot_d: int                      # total delta ms (drv_t - ref_t)
    # Per-sector deltas — usually 3, always short.
    sec_d: list[int]                # e.g. [+120, -30, +410]
    # Aggregate intervention deltas (full lap, not per corner)
    abs_f_d: int                    # abs_total_frames_delta
    tc_f_d:  int                    # tc_total_frames_delta
    lock_d:  int                    # lockup_events_delta
    # Environment only if materially different from reference
    env_note: Optional[str] = None  # e.g. "wet vs dry ref" — omitted when matched

# -------- Tail aggregate for the corners NOT in the top-N --------
class TailAggregate(BaseModel):
    n_corners: int                  # how many corners rolled up here
    t_d_sum:   int                  # summed time delta of the tail (ms)
    dominant_tags: list[str]        # up to 3 most-common tags in the tail

# -------- The full report (this is what the LLM receives) --------
class DeltaReport(BaseModel):
    v: int = 1                      # schema version — bump on breaking change
    hdr: LapDeltaHeader
    top: list[CornerDelta]          # sorted by |t_d| desc, length <= TOP_N (8)
    tail: Optional[TailAggregate] = None
    # Stint-level context: last N laps of the driver, time only.
    # Lets the LLM comment on consistency without per-lap payloads.
    recent_laps_ms: list[int] = Field(default_factory=list)
```

#### 9.3.2 Legend (sent once in system prompt, not per request)

```
LEGEND (all *_d = driver - reference):
  t_d  ms    (+ lost)     bp_d m   (+ later brake)   bd_d ms
  mb_d 0-1  ms_d/xs_d km/h  th_d m (+ later throttle)
  abs_d/tc_d 0-1   slip 0-1 (rear wheels)
  sec_d ms per sector   env_note present only if conditions differ
  tags = fixed vocab hints; empty = clean corner
```

#### 9.3.3 Builder contract (`backend/services/diff.py`)

```python
TOP_N = 8                 # configurable in settings
TAIL_MIN_TIME_MS = 30     # ignore corners whose |t_d| < this entirely

def build_delta_report(
    driver: LapSummary,
    reference: LapSummary,
    recent_laps_ms: list[int],
) -> DeltaReport: ...

def serialize_for_llm(report: DeltaReport) -> str:
    """
    Compact JSON, no whitespace. Rounds floats to the fixed precision in
    TOKEN_PRECISION before dump. Never emits nulls — omits the field instead.
    """
```

Precision rules (enforced in `serialize_for_llm`):

| Field group        | Precision      |
|--------------------|----------------|
| time deltas        | int ms         |
| distance deltas    | 1 dp metre     |
| speed deltas       | 1 dp km/h      |
| input deltas (0-1) | 2 dp           |
| slip / abs / tc    | 2 dp           |

Pass the `DeltaReport` — not the raw laps — to the LLM prompt. The LLM interprets causes
and recommends fixes; it does not do arithmetic. The builder is pure and deterministic so
the same input always yields the same prompt, enabling response caching keyed on the
serialized report hash.

### 9.4 Batching Strategy

Analysis is triggered **after every `upload_after_n_laps` valid laps** (default 3). The
backend selects the driver's **fastest valid lap in the batch** as the delta subject
(unless `AnalysisRequest.focus_lap_number` is set), diffs it against the reference, and
includes the time-only trace of all laps in the batch as `recent_laps_ms` for
consistency commentary. This keeps per-batch prompt size bounded regardless of stint
length.

---

## 9.5 Reference Lap Ingestion from ACC Replays

Reference laps come from **ACC replay files** (`.rpy` in `Documents/Assetto Corsa
Competizione/Replay/Saved/`), not from videos. ACC's replay format is proprietary and
cannot be parsed directly, so the ingestion flow is:

1. User loads the replay in ACC and watches it in spectator mode.
2. `client/replay_ingest/` runs the same shared-memory poller as live driving, but
   tolerates `status == ACC_REPLAY` and records `completedLaps` frames.
3. The resulting frames flow through the normal `summarizer.py` to produce a
   `LapSummary`, which is then POSTed to `/reference-laps` with `source="replay"`.
4. Multiple laps in a replay are eligible — the client picks the fastest valid one by
   default, or lets the user choose via a simple picker UI.

Because reference ingestion reuses the same summarizer, reference and driver laps are
**structurally identical** and the diff engine needs no special-casing. Store the
replay filename in `LapSummary.source_meta` for provenance.

---

## 10. Docker Deployment

### 10.1 `docker-compose.yml`

```yaml
version: "3.9"

services:
  api:
    build: ./backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://acc:${DB_PASSWORD}@db:5432/acc_coaching
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - API_KEY=${API_KEY}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend/prompts:/app/prompts:ro

  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=acc
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=acc_coaching
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U acc -d acc_coaching"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 10.2 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY ../shared ./shared
RUN pip install --no-cache-dir -e ./shared

ENV PYTHONUNBUFFERED=1

RUN alembic upgrade head

CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-"]
```

### 10.3 `.env.example`

```env
# Backend
DATABASE_URL=postgresql+asyncpg://acc:changeme@db:5432/acc_coaching
ANTHROPIC_API_KEY=sk-ant-...
API_KEY=your-secret-key-here
DB_PASSWORD=changeme

# Client (config.toml, not .env)
# BACKEND_URL = "https://your-server.com/api/v1"
# API_KEY = "your-secret-key-here"
```

### 10.4 Deployment Commands

```bash
# On your server
git clone <repo> acc-coaching
cd acc-coaching
cp .env.example .env
# Edit .env with real values

docker compose up -d

# View logs
docker compose logs -f api

# Run migrations manually if needed
docker compose exec api alembic upgrade head
```

---

## 11. Client Configuration (`client/config.toml`)

```toml
[backend]
url = "https://your-server.com/api/v1"
api_key = "your-secret-key-here"
upload_enabled = true
upload_after_n_laps = 3        # Trigger analysis after this many laps

[overlay]
opacity = 0.85
position = "top-right"         # top-left | top-right | bottom-left | bottom-right
show_minimap = true
show_tyre_temps = true
show_delta = true

[audio]
enabled = true
master_volume = 0.8
brake_cues_enabled = true
lockup_cues_enabled = true
flag_cues_enabled = true
fuel_cues_enabled = true

[recording]
sample_rate_hz = 60
corner_speed_threshold_kmh = 180
min_corner_separation_m = 50
lockup_slip_threshold = 0.30

[thresholds]
low_fuel_litres = 5.0
tyre_temp_warn_min_c = 70.0
tyre_temp_warn_max_c = 105.0
```

---

## 12. Key Implementation Rules for Coding Agents

1. **Never write to ACC shared memory.** Read-only access only.
2. **Never pass raw frame arrays to the LLM.** Always summarize first via `summarizer.py` and diff via `diff.py`.
3. **All inter-thread communication uses `queue.Queue`.** No shared mutable state between threads.
4. **Pydantic models in `shared/` are the source of truth for data shapes.** Do not redefine schemas in client or backend independently.
5. **Audio files must be pre-loaded at startup** via `pygame.mixer.Sound()`. Never load from disk on a trigger event.
6. **Guard every shared memory read.** If `OpenFileMapping` returns null (game not running), poll silently and retry — never crash.
7. **SQLite uploads are idempotent.** The uploader checks `uploaded=0` and sets `uploaded=1` only on confirmed HTTP 200/201 from the backend. On failure it retries next cycle.
8. **Backend endpoints return HTTP 422 with detail on schema validation failure.** Use FastAPI's default pydantic validation — do not write custom validation middleware.
9. **All database access in the backend is async.** Use `async with session:` patterns throughout. No synchronous SQLAlchemy calls.
10. **Migrations are managed by Alembic only.** Never use `Base.metadata.create_all()` in production code.
