import json
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.engines.registry import engine_registry
from app.schemas import TTSBatchRequest
from app.services.audio_exporter import export_audio
from app.services.audio_processor import clean_audio, trim_silence

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post("/generate")
async def batch_generate(req: TTSBatchRequest, session: AsyncSession = Depends(get_session)):
    async def stream():
        engine = await engine_registry.get(req.model)
        results = []
        total = len(req.paragraphs)

        for i, paragraph in enumerate(req.paragraphs):
            yield f"data: {json.dumps({'status': 'generating', 'index': i, 'total': total})}\n\n"

            audio, sr = await engine.generate(
                text=paragraph,
                language=req.language,
                speed=req.speed,
                stability=req.stability,
                clarity=req.clarity,
                steps=req.steps,
            )
            audio = trim_silence(audio, sr)
            audio = await clean_audio(audio, sr)

            file_id = str(uuid.uuid4())
            output_path = settings.temp_dir / f"{file_id}.wav"
            await export_audio(audio, sr, output_path)

            duration = len(audio) / sr
            results.append({
                "index": i,
                "audio_url": f"/audio/temp/{file_id}.wav",
                "duration": round(duration, 2),
            })

            yield f"data: {json.dumps({'status': 'completed_segment', 'index': i, 'audio_url': f'/audio/temp/{file_id}.wav', 'duration': round(duration, 2)})}\n\n"

        yield f"data: {json.dumps({'status': 'done', 'segments': results})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
