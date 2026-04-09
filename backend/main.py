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
