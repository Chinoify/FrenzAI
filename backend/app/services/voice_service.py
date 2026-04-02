import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Voice


async def create_voice(
    session: AsyncSession,
    name: str,
    engine: str,
    language: str,
    tags: list[str],
    notes: str,
    embedding: np.ndarray,
    sample_path: Optional[str],
    quality_score: float = 0.0,
) -> Voice:
    voice_id = str(uuid.uuid4())

    # Save embedding
    emb_path = settings.embeddings_dir / f"{voice_id}.npy"
    np.save(str(emb_path), embedding)

    voice = Voice(
        id=voice_id,
        name=name,
        engine=engine,
        language=language,
        tags=tags,
        notes=notes,
        embedding_path=str(emb_path),
        sample_path=sample_path,
        quality_score=quality_score,
    )
    session.add(voice)
    await session.commit()
    await session.refresh(voice)
    return voice


async def get_voice_embedding(voice: Voice) -> Optional[np.ndarray]:
    if voice.embedding_path and Path(voice.embedding_path).exists():
        return np.load(voice.embedding_path)
    return None


async def list_voices(
    session: AsyncSession,
    search: Optional[str] = None,
    engine: Optional[str] = None,
    language: Optional[str] = None,
) -> list[Voice]:
    query = select(Voice).order_by(Voice.is_favorite.desc(), Voice.created_at.desc())
    if search:
        query = query.where(Voice.name.ilike(f"%{search}%"))
    if engine:
        query = query.where(Voice.engine == engine)
    if language:
        query = query.where(Voice.language == language)
    result = await session.execute(query)
    return list(result.scalars().all())
