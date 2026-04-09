"""Analysis router."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.orm import Analysis as AnalysisModel
from shared.models import AnalysisRequest


router = APIRouter(tags=["analysis"])


@router.post("/analysis/session/{session_id}")
async def create_analysis(
    session_id: str,
    payload: AnalysisRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not Implemented -- LLM analysis coming in Phase 3",
    )


@router.get("/analysis/session/{session_id}/latest")
async def get_latest_analysis(session_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    analysis = await db.scalar(
        select(AnalysisModel)
        .where(AnalysisModel.session_id == session_id)
        .order_by(AnalysisModel.generated_at.desc(), AnalysisModel.id.desc())
    )
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis.result
