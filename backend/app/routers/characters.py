"""Character voice assignment for multi-voice audiobook generation."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Chapter, Project

router = APIRouter(prefix="/api/projects/{project_id}/characters", tags=["characters"])


@router.post("/detect")
async def detect_characters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Analyze all chapters to detect dialogue and characters."""
    from app.services.character_detection import detect_characters_and_dialogue, auto_assign_voices

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all chapter text
    result = await session.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.index)
    )
    chapters = list(result.scalars().all())
    full_text = "\n\n".join(ch.text for ch in chapters)

    # Detect characters
    detection = detect_characters_and_dialogue(full_text)
    characters = detection["characters"]

    # Auto-assign voices
    characters = auto_assign_voices(characters)

    # Store in project metadata (using notes field or a new JSON field)
    # We'll store as JSON in the project's params field
    project.params = project.params or {}
    project.params["characters"] = characters
    project.params["has_character_voices"] = True
    await session.commit()

    return {
        "characters": characters,
        "total_characters": len([c for c in characters if not c.get("is_narrator")]),
        "total_segments": len(detection.get("segments", [])),
    }


@router.get("")
async def get_characters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get current character-voice assignments."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    characters = (project.params or {}).get("characters", [])
    return {"characters": characters, "has_character_voices": bool(characters)}


@router.patch("/{character_name}")
async def update_character_voice(
    project_id: str,
    character_name: str,
    req: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update the voice assignment for a character."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    characters = (project.params or {}).get("characters", [])
    updated = False
    for char in characters:
        if char["name"] == character_name:
            if "kokoro_voice_code" in req:
                char["kokoro_voice_code"] = req["kokoro_voice_code"]
            if "voice_id" in req:
                char["voice_id"] = req["voice_id"]
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")

    project.params["characters"] = characters
    await session.commit()

    return {"status": "updated", "character": character_name}


@router.post("/auto-assign")
async def auto_assign(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Auto-assign Kokoro voices to detected characters."""
    from app.services.character_detection import auto_assign_voices

    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    characters = (project.params or {}).get("characters", [])
    if not characters:
        raise HTTPException(status_code=400, detail="No characters detected. Run /detect first.")

    characters = auto_assign_voices(characters)
    project.params["characters"] = characters
    await session.commit()

    return {"characters": characters}


@router.delete("")
async def clear_characters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Clear all character-voice assignments."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.params:
        project.params.pop("characters", None)
        project.params.pop("has_character_voices", None)
    await session.commit()

    return {"status": "cleared"}
