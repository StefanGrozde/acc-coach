"""ACC Coaching Backend API."""
import structlog

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from routers.health import router as health_router
from routers.analysis import router as analysis_router
from routers.laps import router as laps_router
from routers.reference_laps import router as reference_laps_router
from routers.sessions import router as sessions_router

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

api_key_dep = Depends(verify_api_key)
app.include_router(sessions_router, prefix="/api/v1", dependencies=[api_key_dep])
app.include_router(laps_router, prefix="/api/v1", dependencies=[api_key_dep])
app.include_router(analysis_router, prefix="/api/v1", dependencies=[api_key_dep])
app.include_router(reference_laps_router, prefix="/api/v1", dependencies=[api_key_dep])


@app.on_event("startup")
async def startup() -> None:
    logger.info("acc_coaching_api_starting")
