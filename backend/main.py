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
