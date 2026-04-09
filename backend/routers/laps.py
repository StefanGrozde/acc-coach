"""Laps router."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.orm import Lap as LapModel
from models.orm import Session as SessionModel
from shared.models import LapSummary


router = APIRouter(tags=["laps"])


@router.post("/laps", status_code=status.HTTP_201_CREATED)
async def create_lap(payload: LapSummary, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    existing_session = await db.scalar(select(SessionModel).where(SessionModel.session_id == payload.session_id))
    if existing_session is None:
        # The lap payload does not carry session metadata beyond circuit/car, so seed a minimal parent session.
        existing_session = SessionModel(
            session_id=payload.session_id,
            session_type="UNKNOWN",
            circuit=payload.circuit,
            car_model=payload.car_model,
            started_at=payload.recorded_at,
        )
        db.add(existing_session)
        await db.flush()

    lap = LapModel(
        session_id=payload.session_id,
        lap_number=payload.lap_number,
        lap_time_ms=payload.lap_time_ms,
        is_valid=payload.is_valid,
        circuit=payload.circuit,
        car_model=payload.car_model,
        recorded_at=payload.recorded_at,
        summary=payload.model_dump(),
    )
    db.add(lap)
    await db.commit()
    await db.refresh(lap)
    return {
        "id": str(lap.id),
        "session_id": lap.session_id,
        "lap_number": lap.lap_number,
    }


@router.get("/sessions/{session_id}/laps")
async def get_session_laps(session_id: str, db: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await db.scalars(select(LapModel).where(LapModel.session_id == session_id).order_by(LapModel.lap_number))
    return [lap.summary for lap in rows.all()]
