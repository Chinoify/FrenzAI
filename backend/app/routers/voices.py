from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Voice
from app.schemas import VoiceResponse, VoiceUpdate
from app.services.voice_service import list_voices

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("", response_model=list[VoiceResponse])
async def get_voices(
    search: Optional[str] = None,
    engine: Optional[str] = None,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    voices = await list_voices(session, search=search, engine=engine, language=language)
    return [
        VoiceResponse(
            id=v.id,
            name=v.name,
            engine=v.engine,
            language=v.language,
            tags=v.tags or [],
            notes=v.notes or "",
            quality_score=v.quality_score,
            use_count=v.use_count,
            is_favorite=v.is_favorite,
            sample_url=f"/audio/voices/samples/{Path(v.sample_path).name}" if v.sample_path else None,
            created_at=v.created_at,
        )
        for v in voices
    ]


@router.get("/{voice_id}", response_model=VoiceResponse)
async def get_voice(voice_id: str, session: AsyncSession = Depends(get_session)):
    voice = await session.get(Voice, voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        engine=voice.engine,
        language=voice.language,
        tags=voice.tags or [],
        notes=voice.notes or "",
        quality_score=voice.quality_score,
        use_count=voice.use_count,
        is_favorite=voice.is_favorite,
        sample_url=f"/audio/voices/samples/{Path(voice.sample_path).name}" if voice.sample_path else None,
        created_at=voice.created_at,
    )


@router.patch("/{voice_id}", response_model=VoiceResponse)
async def update_voice(
    voice_id: str,
    update: VoiceUpdate,
    session: AsyncSession = Depends(get_session),
):
    voice = await session.get(Voice, voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(voice, field, value)

    await session.commit()
    await session.refresh(voice)
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        engine=voice.engine,
        language=voice.language,
        tags=voice.tags or [],
        notes=voice.notes or "",
        quality_score=voice.quality_score,
        use_count=voice.use_count,
        is_favorite=voice.is_favorite,
        sample_url=f"/audio/voices/samples/{Path(voice.sample_path).name}" if voice.sample_path else None,
        created_at=voice.created_at,
    )


# --- Voice Blending ---
@router.post("/blend")
async def blend_voices(req: dict, session: AsyncSession = Depends(get_session)):
    """Blend 2-4 Kokoro voices into a new custom voice."""
    import uuid as _uuid
    from app.engines.registry import engine_registry
    from app.services.voice_blend_service import blend_kokoro_voices
    from app.engines.kokoro_engine import ALL_VOICES

    voices = req.get("voices", [])
    name = req.get("name", "Blended Voice")
    language = req.get("language", "en")
    tags = req.get("tags", ["blended"])
    notes = req.get("notes", "")

    if len(voices) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 voices")

    for v in voices:
        if v.get("code") not in ALL_VOICES:
            raise HTTPException(status_code=400, detail=f"Unknown voice: {v.get('code')}")

    # Get Kokoro pipeline
    engine = await engine_registry.get("kokoro")
    if not engine._pipeline:
        raise HTTPException(status_code=500, detail="Kokoro engine not loaded")

    blended_tensor, pt_path = await blend_kokoro_voices(voices, engine._pipeline)

    # Create voice DB entry
    voice_id = str(_uuid.uuid4())
    # Build description of blend
    blend_desc = " + ".join(f"{v['code']}({v['weight']:.0%})" for v in voices)
    full_notes = f"Blended: {blend_desc}" + (f"\n{notes}" if notes else "")

    voice = Voice(
        id=voice_id,
        name=name,
        engine="kokoro",
        language=language,
        tags=tags,
        notes=full_notes,
        embedding_path=pt_path,
        quality_score=4.0,
    )
    session.add(voice)
    await session.commit()
    await session.refresh(voice)

    return {
        "id": voice.id,
        "name": voice.name,
        "engine": voice.engine,
        "language": voice.language,
        "notes": voice.notes,
        "status": "created",
    }


# --- Create voice from text description (Parler-TTS) ---
@router.post("/create-from-description")
async def create_voice_from_description(req: dict, session: AsyncSession = Depends(get_session)):
    """Generate a voice from a natural language description using Parler-TTS."""
    import uuid as _uuid
    from app.engines.registry import engine_registry
    from app.services.audio_exporter import export_audio

    description = req.get("description", "")
    name = req.get("name", "Described Voice")
    sample_text = req.get("sample_text", "The quick brown fox jumps over the lazy dog.")
    language = req.get("language", "en")

    if not description:
        raise HTTPException(status_code=400, detail="Voice description is required")

    try:
        engine = await engine_registry.get("parler")
    except Exception:
        raise HTTPException(status_code=400, detail="Parler-TTS not available. Download it from the Models page first.")

    # Generate sample audio
    audio, sr = await engine.generate(
        text=sample_text,
        language=language,
        voice_description=description,
    )

    # Save sample audio
    from app.config import settings
    import numpy as np
    file_id = str(_uuid.uuid4())
    sample_path = settings.samples_dir / f"{file_id}.wav"
    await export_audio(audio, sr, sample_path)

    # Save embedding (store description as bytes for compatibility)
    emb = np.zeros(256, dtype=np.float32)
    desc_bytes = description.encode("utf-8")[:256]
    for i, b in enumerate(desc_bytes):
        emb[i] = float(b)
    emb_path = settings.embeddings_dir / f"{file_id}.npy"
    np.save(str(emb_path), emb)

    voice = Voice(
        id=file_id,
        name=name,
        engine="parler",
        language=language,
        tags=["parler", "text-described"],
        notes=f"Description: {description}",
        embedding_path=str(emb_path),
        sample_path=str(sample_path),
        quality_score=3.5,
    )
    session.add(voice)
    await session.commit()

    return {
        "id": voice.id,
        "name": voice.name,
        "description": description,
        "sample_url": f"/audio/voices/samples/{sample_path.name}",
        "status": "created",
    }


@router.delete("/{voice_id}")
async def delete_voice(voice_id: str, session: AsyncSession = Depends(get_session)):
    voice = await session.get(Voice, voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    # Delete files
    if voice.embedding_path:
        Path(voice.embedding_path).unlink(missing_ok=True)
    if voice.sample_path:
        Path(voice.sample_path).unlink(missing_ok=True)

    await session.delete(voice)
    await session.commit()
    return {"status": "deleted"}
