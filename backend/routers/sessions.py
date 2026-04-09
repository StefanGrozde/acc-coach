"""Sessions router."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.orm import Session as SessionModel


class SessionCreate(BaseModel):
    session_id: str
    session_type: str
    circuit: str
    car_model: str
    started_at: datetime


class SessionRead(BaseModel):
    id: UUID
    session_id: str
    session_type: str | None
    circuit: str | None
    car_model: str | None
    started_at: datetime | None
    created_at: datetime | None


router = APIRouter(tags=["sessions"])


def _serialize_session(session: SessionModel) -> dict[str, object | None]:
    return {
        "id": str(session.id),
        "session_id": session.session_id,
        "session_type": session.session_type,
        "circuit": session.circuit,
        "car_model": session.car_model,
        "started_at": session.started_at,
        "created_at": session.created_at,
    }


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object | None]:
    existing = await db.scalar(select(SessionModel).where(SessionModel.session_id == payload.session_id))
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _serialize_session(existing)

    session = SessionModel(
        session_id=payload.session_id,
        session_type=payload.session_type,
        circuit=payload.circuit,
        car_model=payload.car_model,
        started_at=payload.started_at,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _serialize_session(session)


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, object | None]:
    session = await db.scalar(select(SessionModel).where(SessionModel.session_id == session_id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _serialize_session(session)
