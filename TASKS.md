# TASKS.md

## Sprint 1 — Infrastructure Foundation
Branch: sprint-1-infrastructure
Status: DONE (✓ Remote deployment verified 2026-04-10)

---

### T1.1 — Shared models package + project structure
Status: DONE
Depends on: none

**Context**
This is the first task in a greenfield project. The repository currently contains only `CLAUDE.md`, `SPEC.md`, and `plan/references/planner.md`. You are creating the `shared/` Python package that serves as the single source of truth for all data shapes used by both the client and backend.

The package must be installable via `pip install -e ./shared` so both `client/` and `backend/` can import from it (e.g., `from shared.models import LapSummary`).

All Pydantic models are defined in SPEC.md Section 5.1. You must implement all of them:
- `WheelData`
- `CornerSummary`
- `LapSummary`
- `SessionSummary`
- `AnalysisRequest`
- `CornerFeedback`
- `AnalysisResult`

You must also implement the DeltaReport models from SPEC.md Section 9.3.1:
- `CornerDelta`
- `LapDeltaHeader`
- `TailAggregate`
- `DeltaReport`

Use Pydantic v2 (`from pydantic import BaseModel, Field`). All models use standard Python types. Python version is 3.11+.

You also need to create:
- `pyproject.toml` at the project root with basic project metadata and `ruff` config
- `shared/pyproject.toml` for the shared package installability
- `shared/__init__.py` that re-exports models

**Files**
- CREATE `shared/__init__.py`
- CREATE `shared/models.py`
- CREATE `shared/pyproject.toml`
- CREATE `pyproject.toml`

**Implementation**

1. Create `pyproject.toml` at the project root:
```toml
[project]
name = "acc-coaching"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.mypy]
python_version = "3.11"
strict = true
```

2. Create `shared/pyproject.toml`:
```toml
[project]
name = "acc-shared"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

3. Create `shared/__init__.py`:
```python
from shared.models import (
    AnalysisRequest,
    AnalysisResult,
    CornerDelta,
    CornerFeedback,
    CornerSummary,
    DeltaReport,
    LapDeltaHeader,
    LapSummary,
    SessionSummary,
    TailAggregate,
    WheelData,
)

__all__ = [
    "WheelData",
    "CornerSummary",
    "LapSummary",
    "SessionSummary",
    "AnalysisRequest",
    "CornerFeedback",
    "AnalysisResult",
    "CornerDelta",
    "LapDeltaHeader",
    "TailAggregate",
    "DeltaReport",
]
```

4. Create `shared/models.py` containing all Pydantic v2 models exactly as specified in SPEC.md Sections 5.1 and 9.3.1. Key details:
   - `WheelData`: fields `fl`, `fr`, `rl`, `rr` (all `float`)
   - `CornerSummary`: all fields from SPEC.md Section 5.1, `corner_name` is `Optional[str]`
   - `LapSummary`: all fields from SPEC.md Section 5.1 including `corners: list[CornerSummary]`, `tyre_core_temp_avg: WheelData`, etc.
   - `SessionSummary`: fields `session_id`, `session_type`, `circuit`, `car_model`, `started_at`, `laps: list[LapSummary]`
   - `AnalysisRequest`: `session_id`, optional `reference_lap_id`, optional `focus_areas`
   - `CornerFeedback`: `corner_index`, optional `corner_name`, optional `time_loss_estimate_ms`, `issues`, `recommendations`
   - `AnalysisResult`: all fields from SPEC.md Section 5.1
   - `CornerDelta`: all abbreviated fields from SPEC.md Section 9.3.1 with the `tags` literal list
   - `LapDeltaHeader`: all fields from SPEC.md Section 9.3.1
   - `TailAggregate`: `n_corners`, `t_d_sum`, `dominant_tags`
   - `DeltaReport`: `v`, `hdr`, `top`, `tail`, `recent_laps_ms`
   - All models use `from datetime import datetime`, `from typing import Optional`, `from enum import IntEnum` as needed
   - All models use Pydantic v2 style (no `class Config`, use `model_config` if needed)

**Acceptance Criteria**
- [ ] `pip install -e ./shared` succeeds without errors
- [ ] `python -c "from shared.models import LapSummary, DeltaReport"` succeeds
- [ ] All model fields match SPEC.md Sections 5.1 and 9.3.1 exactly
- [ ] `ruff check shared/` passes with zero errors

---

### T1.2 — Docker Compose + Dockerfile + .env.example
Status: DONE
Depends on: T1.1

**Context**
Create the Docker infrastructure for the backend API and PostgreSQL database. The backend is a FastAPI application served by gunicorn with uvicorn workers. PostgreSQL 15 is used for data storage.

The `shared/` package (created in T1.1) must be installed inside the Docker container so the backend can import from it. The Dockerfile copies `shared/` into the container and runs `pip install -e ./shared`.

The Docker Compose file defines two services: `api` and `db`. The API service waits for the database to be healthy before starting. Environment variables are loaded from a `.env` file.

The backend directory structure you are creating:
```
backend/
  main.py          (placeholder -- just enough to import, will be filled in T1.4)
  requirements.txt
  Dockerfile
```

**Files**
- CREATE `docker-compose.yml`
- CREATE `backend/Dockerfile`
- CREATE `backend/requirements.txt`
- CREATE `backend/main.py` (minimal placeholder)
- CREATE `.env.example`

**Implementation**

1. Create `docker-compose.yml` at project root:
```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: backend/Dockerfile
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

2. Create `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install shared package first (for caching)
COPY shared/ ./shared/
RUN pip install --no-cache-dir -e ./shared

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create prompts directory
RUN mkdir -p /app/prompts

ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-"]
```

3. Create `backend/requirements.txt`:
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
gunicorn>=21.2.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.12.0
pydantic>=2.0
pydantic-settings>=2.0
python-dotenv>=1.0.0
structlog>=23.0
httpx>=0.25.0
```

4. Create `backend/main.py` as a minimal placeholder:
```python
"""ACC Coaching Backend API — Phase 1 placeholder."""
from fastapi import FastAPI

app = FastAPI(
    title="ACC Coaching API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

5. Create `.env.example`:
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

**Acceptance Criteria**
- [ ] `docker compose build` succeeds (builds the API image)
- [ ] `docker compose up -d` starts both `api` and `db` containers
- [ ] `GET http://localhost:8000/api/v1/health` returns `{"status": "ok"}`
- [ ] `docker compose down -v` cleans up containers and volumes

---

### T1.3 — Database session, Alembic setup, initial migration
Status: DONE
NOTE: ORM models missing ForeignKey() definitions; migration is correct. Fix before Phase 2.
Depends on: T1.2

**Context**
Set up async SQLAlchemy database access and Alembic migrations for the PostgreSQL backend. The initial migration must create all four tables specified in SPEC.md Section 5.3:
- `sessions` (columns: id UUID PK, session_id TEXT UNIQUE, session_type TEXT, circuit TEXT, car_model TEXT, started_at TIMESTAMPTZ, created_at TIMESTAMPTZ)
- `laps` (columns: id UUID PK, session_id TEXT FK->sessions, lap_number INT, lap_time_ms INT, is_valid BOOLEAN, circuit TEXT, car_model TEXT, recorded_at TIMESTAMPTZ, summary JSONB, created_at TIMESTAMPTZ; UNIQUE constraint on session_id+lap_number)
- `analyses` (columns: id UUID PK, session_id TEXT FK->sessions, generated_at TIMESTAMPTZ, result JSONB, model_used TEXT, prompt_tokens INT, completion_tokens INT)
- `reference_laps` (columns: id UUID PK, circuit TEXT, car_model TEXT, lap_time_ms INT, source TEXT, summary JSONB, added_at TIMESTAMPTZ)
- Indexes: `idx_laps_session` on laps(session_id), `idx_laps_circuit_car` on laps(circuit, car_model), `idx_analyses_session` on analyses(session_id)

The database session module provides an async `get_db()` dependency for FastAPI. The engine reads `DATABASE_URL` from the environment.

Alembic must be configured for async operation (using `asyncpg` driver). The `alembic.ini` lives in `backend/`. The `env.py` must import the ORM models' `Base.metadata` for autogenerate support.

**Files**
- CREATE `backend/db/__init__.py`
- CREATE `backend/db/session.py`
- CREATE `backend/models/__init__.py`
- CREATE `backend/models/orm.py`
- CREATE `backend/alembic.ini`
- CREATE `backend/db/migrations/env.py`
- CREATE `backend/db/migrations/script.py.mako`
- CREATE `backend/db/migrations/versions/__init__.py` (empty)
- Run `alembic revision --autogenerate -m "initial"` to create the migration

**Implementation**

1. Create `backend/db/__init__.py` (empty).

2. Create `backend/db/session.py`:
```python
"""Async SQLAlchemy engine and session factory."""
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://acc:changeme@localhost:5432/acc_coaching",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        yield session
```

3. Create `backend/models/__init__.py` (empty).

4. Create `backend/models/orm.py` with SQLAlchemy ORM models matching SPEC.md Section 5.3. Use `UUID` columns with `server_default=func.gen_random_uuid()`. Import `Guid` server default from SQLAlchemy. Key details:
   - Import `from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Index, UniqueConstraint`
   - Import `from sqlalchemy.dialects.postgresql import UUID, JSONB`
   - Import `from sqlalchemy.sql import func`
   - Import `from sqlalchemy.orm import DeclarativeBase`
   - Define `class Base(DeclarativeBase)` with no custom config
   - Define `Session`, `Lap`, `Analysis`, `ReferenceLap` classes
   - `Lap.summary` is `Column(JSONB, nullable=False)`
   - `Analysis.result` is `Column(JSONB, nullable=False)`
   - `ReferenceLap.summary` is `Column(JSONB, nullable=False)`
   - Add indexes and unique constraints as specified

5. Create `backend/alembic.ini`:
```ini
[alembic]
script_location = db/migrations
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://acc:changeme@localhost:5432/acc_coaching

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

6. Create `backend/db/migrations/env.py` configured for async Alembic:
   - Import `asyncio` and `from logging.config import fileConfig`
   - Import `from sqlalchemy.ext.asyncio import create_async_engine`
   - Import `from models.orm import Base` (the ORM declarative base)
   - Import `from alembic import context`
   - Set `target_metadata = Base.metadata`
   - Implement `run_migrations_online()` using async engine with `connect()` and `connection.run_sync(do_run_migrations)`
   - Read `DATABASE_URL` from environment (override `sqlalchemy.url` from ini)

7. Create `backend/db/migrations/script.py.mako` (standard Alembic Mako template).

8. Create `backend/db/migrations/versions/__init__.py` (empty file).

9. Run from within the backend directory (or via docker):
   ```
   cd backend && alembic revision --autogenerate -m "initial"
   ```
   This creates the initial migration file in `backend/db/migrations/versions/`.

**Acceptance Criteria**
- [ ] `alembic revision --autogenerate -m "test"` detects all four tables without unexpected drops
- [ ] `alembic upgrade head` runs without errors against a running PostgreSQL instance
- [ ] `\dt` in PostgreSQL shows `sessions`, `laps`, `analyses`, `reference_laps` tables
- [ ] All indexes from SPEC.md Section 5.3 exist

---

### T1.4 — Backend API skeleton with health endpoint + API key auth
Status: DONE
Depends on: T1.3

**Context**
Replace the placeholder `backend/main.py` with a full FastAPI application skeleton that includes:
- App factory or module-level app with routers
- API key authentication middleware (read `API_KEY` from env, validate `X-API-Key` header on all routes except `/health`)
- CORS middleware (allow all origins for Phase 1 -- the scaffolding UI needs it)
- Structlog configuration
- Mounting routers under `/api/v1` prefix
- The `db/session.py` `get_db()` dependency integrated

For this task, create a minimal `health` router and the auth dependency. The full routers (sessions, laps, analysis, reference-laps) come in T1.5.

The auth mechanism is simple: read `X-API-Key` header from the request, compare it to `API_KEY` environment variable. Return HTTP 401 if missing or mismatched. Use FastAPI's `Security` with `APIKeyHeader`.

**Files**
- MODIFY `backend/main.py`
- CREATE `backend/auth.py`
- CREATE `backend/routers/__init__.py`
- CREATE `backend/routers/health.py`

**Implementation**

1. Create `backend/auth.py`:
```python
"""API key authentication for FastAPI."""
import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Verify the X-API-Key header. Raises 401 if invalid."""
    if not API_KEY:
        # If no API_KEY configured, skip auth (dev mode)
        return "dev"
    if api_key is None or not secrets.compare_digest(api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
```

2. Create `backend/routers/__init__.py` (empty).

3. Create `backend/routers/health.py`:
```python
"""Health check router."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

4. Rewrite `backend/main.py`:
```python
"""ACC Coaching Backend API."""
import structlog

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.health import router as health_router

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()

app = FastAPI(
    title="ACC Coaching API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check does NOT require auth
app.include_router(health_router, prefix="/api/v1")

# Future routers (T1.5) will be added here with auth dependency:
# app.include_router(sessions_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.on_event("startup")
async def startup() -> None:
    logger.info("acc_coaching_api_starting")
```

**Acceptance Criteria**
- [ ] `GET /api/v1/health` returns 200 without any auth header
- [ ] `GET /api/v1/docs` returns the OpenAPI Swagger UI
- [ ] `POST /api/v1/sessions` without `X-API-Key` returns 401 (once T1.5 routers are added, but the auth module must be importable now)
- [ ] CORS headers are present in responses (`Access-Control-Allow-Origin: *`)

---

### T1.5 — Full API routers (sessions, laps, analysis, reference-laps)
Status: DONE
Depends on: T1.4

**Context**
Implement all API routers specified in SPEC.md Section 6. Each router uses the `verify_api_key` dependency from `backend/auth.py` (except health). All database operations use the async `get_db()` session from `backend/db/session.py`.

The routers are:
1. **sessions** -- `POST /sessions`, `GET /sessions/{session_id}`
2. **laps** -- `POST /laps`, `GET /sessions/{session_id}/laps`
3. **analysis** -- `POST /analysis/session/{session_id}`, `GET /analysis/session/{session_id}/latest`
4. **reference-laps** -- `GET /reference-laps`, `POST /reference-laps`

For Phase 1, the analysis POST endpoint returns HTTP 501 "Not Implemented -- LLM analysis coming in Phase 3". The analysis GET endpoint returns the latest analysis from DB if one exists (it won't yet, so it returns 404).

The `POST /laps` endpoint accepts a `LapSummary` JSON body (from `shared.models`), stores it in the `laps` table with the `summary` column as JSONB, and auto-creates the parent `session` row if it doesn't exist (upsert).

The `POST /sessions` endpoint creates a session row. If the session already exists (by `session_id`), return the existing one with HTTP 200 instead of creating a duplicate.

Create placeholder files for services:
- `backend/services/__init__.py` (empty)
- `backend/services/llm.py` (empty -- just a docstring saying "Phase 3")
- `backend/services/diff.py` (empty -- just a docstring saying "Phase 3")

Also create:
- `backend/prompts/` directory (empty, mounted as volume in Docker)
- `backend/prompts/.gitkeep`

**Files**
- CREATE `backend/routers/sessions.py`
- CREATE `backend/routers/laps.py`
- CREATE `backend/routers/analysis.py`
- CREATE `backend/routers/reference_laps.py`
- CREATE `backend/services/__init__.py`
- CREATE `backend/services/llm.py`
- CREATE `backend/services/diff.py`
- CREATE `backend/prompts/.gitkeep`
- MODIFY `backend/main.py` (register new routers)

**Implementation**

1. Create `backend/services/__init__.py` (empty).

2. Create `backend/services/llm.py`:
```python
"""LLM analysis service -- Phase 3 implementation."""
```

3. Create `backend/services/diff.py`:
```python
"""Delta report diff engine -- Phase 3 implementation."""
```

4. Create `backend/prompts/.gitkeep` (empty file).

5. Create `backend/routers/sessions.py`:
   - `POST /sessions` -- accepts `{ session_id, session_type, circuit, car_model, started_at }`, checks if session exists by `session_id`, returns existing (200) or creates new (201)
   - `GET /sessions/{session_id}` -- returns session or 404
   - Use `from models.orm import Session as SessionModel`
   - Use `from db.session import get_db`
   - Use `from auth import verify_api_key` as a dependency
   - Response models: simple dict/Pydantic response models

6. Create `backend/routers/laps.py`:
   - `POST /laps` -- accepts a `LapSummary` JSON body from `shared.models`, creates a `Lap` ORM object with `summary` as JSONB, also auto-creates session if not exists (upsert session row). Returns `{ id, session_id, lap_number }` with 201
   - `GET /sessions/{session_id}/laps` -- returns list of lap summaries from DB
   - Import `from shared.models import LapSummary`

7. Create `backend/routers/analysis.py`:
   - `POST /analysis/session/{session_id}` -- accepts optional `AnalysisRequest` body, returns HTTP 501 with `{"detail": "Not Implemented -- LLM analysis coming in Phase 3"}`
   - `GET /analysis/session/{session_id}/latest` -- queries `analyses` table for latest by `session_id`, returns result or 404

8. Create `backend/routers/reference_laps.py`:
   - `GET /reference-laps` -- accepts optional query params `circuit` and `car_model`, returns matching reference laps from DB
   - `POST /reference-laps` -- accepts `{ circuit, car_model, lap_time_ms, source, summary }`, creates row, returns 201

9. Modify `backend/main.py` to register all routers:
   ```python
   from fastapi import Depends
   from auth import verify_api_key
   from routers.sessions import router as sessions_router
   from routers.laps import router as laps_router
   from routers.analysis import router as analysis_router
   from routers.reference_laps import router as reference_laps_router

   # ... after health router ...

   api_key_dep = Depends(verify_api_key)
   app.include_router(sessions_router, prefix="/api/v1", dependencies=[api_key_dep])
   app.include_router(laps_router, prefix="/api/v1", dependencies=[api_key_dep])
   app.include_router(analysis_router, prefix="/api/v1", dependencies=[api_key_dep])
   app.include_router(reference_laps_router, prefix="/api/v1", dependencies=[api_key_dep])
   ```

**Acceptance Criteria**
- [ ] `POST /api/v1/sessions` with valid `X-API-Key` and body `{"session_id": "test-uuid", "session_type": "PRACTICE", "circuit": "spa", "car_model": "Ferrari 296 GT3", "started_at": "2026-04-09T12:00:00Z"}` returns 201
- [ ] `POST /api/v1/sessions` with same `session_id` returns 200 (idempotent)
- [ ] `POST /api/v1/laps` with a valid LapSummary JSON body returns 201
- [ ] `GET /api/v1/sessions/{session_id}/laps` returns the uploaded lap(s)
- [ ] `POST /api/v1/analysis/session/{session_id}` returns 501
- [ ] `GET /api/v1/analysis/session/{session_id}/latest` returns 404
- [ ] `GET /api/v1/reference-laps` returns empty list `[]`
- [ ] All endpoints return 401 without `X-API-Key` header (except `/health`)

---

### T1.6 — Client scaffolding UI — PyQt6 connection tester
Status: DONE
Depends on: T1.1

**Context**
Create a minimal PyQt6 desktop application that lets a developer test connectivity to the remote backend. This is NOT the final overlay -- it is a throwaway scaffolding tool for Phase 1 verification.

The UI has:
- A text input for the backend base URL (default: `http://localhost:8000/api/v1`)
- A text input for the API key
- A "Test Connection" button that calls `GET /health` (no auth required)
- A "Test Auth" button that calls `GET /sessions` with the API key
- A status label showing the result

The app reads default values from `client/config.toml` if it exists.

Create the full directory structure for the client, but only populate what's needed:
- `client/main.py` -- entry point for the scaffold UI
- `client/config.toml` -- minimal backend config
- `client/scaffold_ui/` -- the scaffolding window
- Empty `__init__.py` files for future client subpackages (poller, recorder, audio, overlay, store, sync)

Use `httpx` for HTTP requests (async, matching the full client's future HTTP client).

**Files**
- CREATE `client/__init__.py`
- CREATE `client/main.py`
- CREATE `client/config.toml`
- CREATE `client/scaffold_ui/__init__.py`
- CREATE `client/scaffold_ui/connection_tester.py`
- CREATE `client/poller/__init__.py`
- CREATE `client/recorder/__init__.py`
- CREATE `client/audio/__init__.py`
- CREATE `client/overlay/__init__.py`
- CREATE `client/store/__init__.py`
- CREATE `client/sync/__init__.py`

**Implementation**

1. Create all empty `__init__.py` files listed above.

2. Create `client/config.toml`:
```toml
[backend]
url = "http://localhost:8000/api/v1"
api_key = "your-secret-key-here"
upload_enabled = true
upload_after_n_laps = 3
```

3. Create `client/scaffold_ui/connection_tester.py`:
   - A PyQt6 `QWidget` subclass called `ConnectionTesterWindow`
   - Layout (vertical):
     - Label "Backend URL:" + QLineEdit (default from config.toml)
     - Label "API Key:" + QLineEdit (echo mode password, default from config.toml)
     - Horizontal row with two buttons: "Test Health" and "Test Auth"
     - QLabel for status output (word wrap, monospace font)
   - `Test Health` handler: uses `httpx.get(f"{url}/health")`, displays response status and body
   - `Test Auth` handler: uses `httpx.get(f"{url}/sessions/nonexistent-test", headers={"X-API-Key": api_key})`, displays 404 (auth works) or 401 (auth failed)
   - Use synchronous `httpx` (not async) for simplicity in PyQt6
   - Parse config.toml using `tomllib` on Python 3.11+

4. Create `client/main.py`:
```python
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
```

**Acceptance Criteria**
- [ ] `python client/main.py` opens a PyQt6 window without errors
- [ ] Window shows URL and API key inputs with defaults from `config.toml`
- [ ] "Test Health" button shows `{"status": "ok"}` when backend is running
- [ ] "Test Auth" button shows "401 Unauthorized" when API key is wrong, or "404" (meaning auth passed) when key is correct
- [ ] Window closes cleanly without errors

---

## Post-Sprint Verification Steps

After all tasks are complete:

1. **Local smoke test**:
   ```bash
   # Start backend
   docker compose up -d
   # Wait for healthy
   curl http://localhost:8000/api/v1/health

   # Test with API key
   curl -H "X-API-Key: test-key" -X POST http://localhost:8000/api/v1/sessions \
     -H "Content-Type: application/json" \
     -d '{"session_id":"test-1","session_type":"PRACTICE","circuit":"spa","car_model":"Ferrari 296 GT3","started_at":"2026-04-09T12:00:00Z"}'

   # Run scaffolding UI
   cd client && python main.py
   ```

2. **Remote deployment test**:
   - Clone repo on remote server
   - `cp .env.example .env` and fill in real values
   - `docker compose up -d`
   - From local machine, update `client/config.toml` with remote URL
   - Test via scaffolding UI

3. **Lint and type check**:
   ```bash
   ruff check .
   mypy shared/ backend/
   ```
