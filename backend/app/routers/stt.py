"""Speech-to-Text API — Whisper transcription."""
import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings

router = APIRouter(prefix="/api/stt", tags=["stt"])

# Lazy-loaded STT model
_stt_model = None
_stt_model_size = None


def _get_stt_model(model_size: str = "base"):
    """Lazy-load faster-whisper model."""
    global _stt_model, _stt_model_size

    if _stt_model is not None and _stt_model_size == model_size:
        return _stt_model

    try:
        from faster_whisper import WhisperModel
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"

        print(f"[STT] Loading Whisper {model_size} on {device}...")
        _stt_model = WhisperModel(model_size, device=device, compute_type=compute)
        _stt_model_size = model_size
        print(f"[STT] Whisper {model_size} ready")
        return _stt_model

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="faster-whisper not installed. Run: pip install faster-whisper"
        )


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model_size: str = Form("base"),
):
    """Transcribe an audio file to text.

    Returns text, segments with timestamps, detected language, word count.
    """
    start = time.time()

    # Save upload
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    upload_path = settings.temp_dir / f"stt_{upload_id}.{ext}"

    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    # Transcribe
    try:
        model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _get_stt_model(model_size)
        )

        lang = None if language == "auto" else language

        def _transcribe():
            segments_list, info = model.transcribe(
                str(upload_path),
                language=lang,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
            )
            segments = []
            full_text = []
            for seg in segments_list:
                segments.append({
                    "start_sec": round(seg.start, 2),
                    "end_sec": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                full_text.append(seg.text.strip())

            text = " ".join(full_text)
            return text, segments, info

        text, segments, info = await asyncio.get_event_loop().run_in_executor(None, _transcribe)

        duration_sec = segments[-1]["end_sec"] if segments else 0
        processing_time = round(time.time() - start, 2)

        return {
            "text": text,
            "segments": segments,
            "language_detected": info.language if hasattr(info, 'language') else language,
            "confidence": round(info.language_probability, 2) if hasattr(info, 'language_probability') else 0,
            "duration_sec": round(duration_sec, 2),
            "word_count": len(text.split()),
            "processing_time_sec": processing_time,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        upload_path.unlink(missing_ok=True)


@router.post("/transcribe-stream")
async def transcribe_stream(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model_size: str = Form("base"),
):
    """Transcribe with SSE streaming — segments appear as they're processed."""
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    upload_path = settings.temp_dir / f"stt_{upload_id}.{ext}"

    content = await file.read()
    with open(upload_path, "wb") as f:
        f.write(content)

    async def stream():
        try:
            model = _get_stt_model(model_size)
            lang = None if language == "auto" else language

            yield f"data: {json.dumps({'status': 'loading', 'message': 'Loading audio...'})}\n\n"

            segments_iter, info = model.transcribe(
                str(upload_path), language=lang, beam_size=5,
                word_timestamps=True, vad_filter=True,
            )

            yield f"data: {json.dumps({'status': 'transcribing', 'language': info.language if hasattr(info, 'language') else 'unknown'})}\n\n"

            full_text = []
            for seg in segments_iter:
                text = seg.text.strip()
                full_text.append(text)
                yield f"data: {json.dumps({'status': 'segment', 'start': round(seg.start, 2), 'end': round(seg.end, 2), 'text': text})}\n\n"

            yield f"data: {json.dumps({'status': 'done', 'text': ' '.join(full_text), 'word_count': len(' '.join(full_text).split())})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            upload_path.unlink(missing_ok=True)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/models")
async def list_stt_models():
    """List available Whisper model sizes with info."""
    models = [
        {"name": "tiny", "size_mb": 75, "accuracy": "Low", "speed": "Fastest", "downloaded": False},
        {"name": "base", "size_mb": 145, "accuracy": "Good", "speed": "Fast", "downloaded": False},
        {"name": "small", "size_mb": 465, "accuracy": "Better", "speed": "Medium", "downloaded": False},
        {"name": "medium", "size_mb": 1500, "accuracy": "High", "speed": "Slow", "downloaded": False},
        {"name": "large-v3", "size_mb": 3000, "accuracy": "Best", "speed": "Slowest", "downloaded": False},
    ]

    # Check which are downloaded
    try:
        from faster_whisper.utils import download_model
        import os
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        for m in models:
            # faster-whisper caches models in HF hub
            model_name = f"models--Systran--faster-whisper-{m['name']}"
            m["downloaded"] = os.path.isdir(os.path.join(cache_dir, model_name))
    except Exception:
        pass

    return {"models": models}
