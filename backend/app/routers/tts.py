import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.db.models import GenerationHistory, Voice
from app.engines.registry import engine_registry
from app.schemas import TTSGenerateRequest, TTSGenerateResponse
from app.services.audio_exporter import export_audio
from app.services.audio_processor import clean_audio, trim_silence
from app.services.voice_service import get_voice_embedding

router = APIRouter(prefix="/api/tts", tags=["tts"])


# --- Fast voice preview with caching ---
_preview_cache: dict[str, str] = {}  # voice_code -> audio_url


@router.get("/preview/{voice_code}")
async def preview_voice(voice_code: str):
    """Generate a quick voice preview. Results are cached for instant replay."""
    import numpy as np

    # Check cache first
    if voice_code in _preview_cache:
        cached_path = settings.temp_dir / _preview_cache[voice_code]
        if cached_path.exists():
            return {"audio_url": f"/audio/temp/{_preview_cache[voice_code]}"}

    from app.engines.kokoro_engine import ALL_VOICES
    if voice_code not in ALL_VOICES:
        raise HTTPException(status_code=404, detail=f"Voice not found: {voice_code}")

    start = time.time()

    # Use a very short sentence for speed
    preview_text = "The quick brown fox jumps over the lazy dog."

    try:
        engine = await engine_registry.get("kokoro")
        audio, sr = await engine.generate(
            text=preview_text,
            language="en",
            speed=1.0,
            kokoro_voice=voice_code,
        )

        # Light normalize only
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * 0.9

        file_id = f"preview_{voice_code}"
        output_path = settings.temp_dir / f"{file_id}.wav"
        await export_audio(audio, sr, output_path)

        # Cache it
        _preview_cache[voice_code] = f"{file_id}.wav"

        return {
            "audio_url": f"/audio/temp/{file_id}.wav",
            "duration": round(len(audio) / sr, 2),
            "generation_time": round(time.time() - start, 2),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_speech(
    req: TTSGenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    start = time.time()

    # Resolve engine + voice
    from app.engines.kokoro_engine import ALL_VOICES
    kokoro_voice = None
    engine_name = req.model or "kokoro"
    voice_name = None
    voice_embedding = None
    sample_path = None
    embedding_path = None

    if req.voice_id:
        if req.voice_id in ALL_VOICES:
            # Kokoro voice code selected directly
            kokoro_voice = req.voice_id
            engine_name = "kokoro"
            voice_name = req.voice_id
        elif req.voice_id.startswith("kokoro:"):
            kokoro_voice = req.voice_id.split(":", 1)[1]
            engine_name = "kokoro"
            voice_name = kokoro_voice
        else:
            # DB voice (cloned) — use a cloning-capable engine
            voice = await session.get(Voice, req.voice_id)
            if not voice:
                raise HTTPException(status_code=404, detail="Voice not found")
            voice_embedding = await get_voice_embedding(voice)
            voice_name = voice.name
            sample_path = voice.sample_path
            embedding_path = voice.embedding_path
            # Override engine if the selected one can't do voice cloning
            CLONING_ENGINES = {"chatterbox", "f5tts", "qwen3tts", "fishspeech", "fish-speech"}
            if engine_name not in CLONING_ENGINES:
                engine_name = voice.engine or "chatterbox"
            voice.use_count += 1
            await session.commit()

    print(f"\n[TTS] model={req.model} voice_id={req.voice_id} -> engine={engine_name} voice={voice_name} sample={sample_path}\n", flush=True)

    # Get engine
    try:
        engine = await engine_registry.get(engine_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load {engine_name}: {e}. Try 'kokoro' or 'builtin'.")

    # Generate audio with clear error
    try:
        audio, sample_rate = await engine.generate(
            text=req.text,
            voice_embedding=voice_embedding,
            language=req.language,
            speed=req.speed,
            stability=req.stability,
            clarity=req.clarity,
            steps=req.steps,
            sample_path=sample_path,
            embedding_path=embedding_path,
            kokoro_voice=kokoro_voice,
        )
    except Exception as e:
        # Reset CUDA on error to prevent cascading failures
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Generation failed ({engine_name}): {e}")

    # Post-process
    audio = trim_silence(audio, sample_rate)
    # Skip aggressive noise reduction for high-quality engines
    if engine_name in ("kokoro", "chatterbox"):
        from app.services.audio_processor import normalize
        audio = normalize(audio, target_db=-3.0)
    else:
        audio = await clean_audio(audio, sample_rate)

    # Save to file
    file_id = str(uuid.uuid4())
    output_path = settings.temp_dir / f"{file_id}.wav"
    await export_audio(audio, sample_rate, output_path)

    duration = len(audio) / sample_rate
    gen_time = time.time() - start

    # Save to history
    history = GenerationHistory(
        text_preview=req.text[:100],
        voice_name=voice_name or "Default",
        model=req.model,
        audio_path=str(output_path),
        duration_seconds=round(duration, 2),
    )
    session.add(history)
    await session.commit()

    audio_url = f"/audio/temp/{file_id}.wav"

    return TTSGenerateResponse(
        audio_url=audio_url,
        duration=round(duration, 2),
        generation_time=round(gen_time, 2),
    )
