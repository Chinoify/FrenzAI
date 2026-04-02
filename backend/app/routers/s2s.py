"""Speech-to-Speech API — transcribe + re-render in a different voice."""
import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.db.models import Voice
from app.services.audio_exporter import export_audio
from app.services.audio_processor import trim_silence, normalize

router = APIRouter(prefix="/api/s2s", tags=["s2s"])


@router.post("/convert")
async def speech_to_speech(
    file: UploadFile = File(...),
    target_voice_id: str = Form(""),
    model: str = Form("kokoro"),
    language: str = Form("en"),
    session: AsyncSession = Depends(get_session),
):
    """Convert speech: transcribe input audio → re-render in target voice.

    1. Transcribe with Whisper
    2. Generate with TTS using target voice
    3. Return both transcript and new audio
    """
    start = time.time()

    # Save upload
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    upload_path = settings.temp_dir / f"s2s_input_{upload_id}.{ext}"

    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Step 1: Transcribe
    try:
        from app.routers.stt import _get_stt_model
        stt_model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _get_stt_model("base")
        )

        def _transcribe():
            segments, info = stt_model.transcribe(str(upload_path), language=language, beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments)
            return text

        transcript = await asyncio.get_event_loop().run_in_executor(None, _transcribe)

        if not transcript.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        upload_path.unlink(missing_ok=True)

    # Get input duration
    try:
        import soundfile as sf
        data, sr = sf.read(str(upload_path))
        input_duration_ms = int(len(data) / sr * 1000)
    except Exception:
        input_duration_ms = 0

    # Step 2: Generate with TTS
    try:
        from app.engines.registry import engine_registry
        from app.services.voice_service import get_voice_embedding

        engine = await engine_registry.get(model)

        voice_embedding = None
        sample_path = None
        kokoro_voice = None

        if target_voice_id:
            # Check if it's a Kokoro voice code
            from app.engines.kokoro_engine import ALL_VOICES
            if target_voice_id in ALL_VOICES:
                kokoro_voice = target_voice_id
            else:
                voice = await session.get(Voice, target_voice_id)
                if voice:
                    voice_embedding = await get_voice_embedding(voice)
                    sample_path = voice.sample_path

        import numpy as np
        audio, sr = await engine.generate(
            text=transcript,
            voice_embedding=voice_embedding,
            language=language,
            speed=1.0,
            sample_path=sample_path,
            kokoro_voice=kokoro_voice,
        )

        # Post-process
        audio = trim_silence(audio, sr)
        audio = normalize(audio, target_db=-3.0)

        # Save output
        output_id = str(uuid.uuid4())
        output_path = settings.temp_dir / f"s2s_output_{output_id}.wav"
        await export_audio(audio, sr, output_path)

        duration_ms = int(len(audio) / sr * 1000)

        return {
            "transcript": transcript,
            "audio_url": f"/audio/temp/{output_path.name}",
            "input_duration_ms": input_duration_ms,
            "output_duration_ms": duration_ms,
            "processing_time_sec": round(time.time() - start, 2),
            "model": model,
            "voice_id": target_voice_id or "default",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech generation failed: {e}")
