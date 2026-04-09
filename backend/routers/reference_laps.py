"""Reference laps router."""
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.orm import ReferenceLap as ReferenceLapModel


class ReferenceLapCreate(BaseModel):
    circuit: str
    car_model: str
    lap_time_ms: int
    source: str
    summary: dict[str, Any]


router = APIRouter(tags=["reference-laps"])


@router.get("/reference-laps")
async def list_reference_laps(
    circuit: str | None = Query(default=None),
    car_model: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(ReferenceLapModel)
    if circuit is not None:
        stmt = stmt.where(ReferenceLapModel.circuit == circuit)
    if car_model is not None:
        stmt = stmt.where(ReferenceLapModel.car_model == car_model)
    rows = await db.scalars(stmt.order_by(ReferenceLapModel.added_at.desc()))
    return [
        {
            "id": str(row.id),
            "circuit": row.circuit,
            "car_model": row.car_model,
            "lap_time_ms": row.lap_time_ms,
            "source": row.source,
            "summary": row.summary,
            "added_at": row.added_at,
        }
        for row in rows.all()
    ]


@router.post("/reference-laps", status_code=status.HTTP_201_CREATED)
async def create_reference_lap(
    payload: ReferenceLapCreate, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    row = ReferenceLapModel(
        circuit=payload.circuit,
        car_model=payload.car_model,
        lap_time_ms=payload.lap_time_ms,
        source=payload.source,
        summary=payload.summary,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": str(row.id),
        "circuit": row.circuit,
        "car_model": row.car_model,
        "lap_time_ms": row.lap_time_ms,
        "source": row.source,
        "summary": row.summary,
        "added_at": row.added_at,
    }
