from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import GenerationHistory
from app.schemas import HistoryResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryResponse])
async def get_history(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    query = (
        select(GenerationHistory)
        .order_by(GenerationHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    entries = result.scalars().all()
    return [
        HistoryResponse(
            id=e.id,
            text_preview=e.text_preview,
            voice_name=e.voice_name,
            model=e.model,
            audio_url=f"/audio/temp/{Path(e.audio_path).name}" if e.audio_path else None,
            duration_seconds=e.duration_seconds,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.delete("/{history_id}")
async def delete_history(history_id: int, session: AsyncSession = Depends(get_session)):
    entry = await session.get(GenerationHistory, history_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    if entry.audio_path:
        Path(entry.audio_path).unlink(missing_ok=True)
    await session.delete(entry)
    await session.commit()
    return {"status": "deleted"}
