import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Project


async def create_project(
    session: AsyncSession,
    name: str,
    text: str,
    voice_id: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "en",
    params: dict = {},
) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        name=name,
        text=text,
        voice_id=voice_id,
        model=model,
        language=language,
        params=params,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def save_project_segments(
    session: AsyncSession,
    project_id: str,
    segments: list[dict],
    merged_audio_path: Optional[str] = None,
) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError(f"Project '{project_id}' not found")
    project.segments = segments
    project.merged_audio_path = merged_audio_path
    await session.commit()
    await session.refresh(project)
    return project
