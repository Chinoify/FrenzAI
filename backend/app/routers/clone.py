import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

import numpy as np

from app.config import settings
from app.db.database import get_session
from app.schemas import VoiceResponse
from app.services.voice_service import create_voice

router = APIRouter(prefix="/api/clone", tags=["clone"])

# Staging directory for uploads that persist across page navigation
STAGING_DIR = settings.base_dir / "data" / "voices" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _get_duration(filepath: Path) -> float | None:
    """Get audio duration via ffprobe (fast, no decode)."""
    import subprocess
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(filepath)],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except Exception:
        pass
    return None


def _convert_and_trim(src: Path, dst: Path, target_seconds: float = 60):
    """Convert any audio to WAV and trim the center segment in a single ffmpeg pass.
    Files <= target_seconds are assumed manually trimmed and left as-is."""
    import subprocess

    duration = _get_duration(src)

    cmd = ["ffmpeg", "-y", "-i", str(src)]

    if duration and duration > target_seconds:
        start = (duration - target_seconds) / 2
        cmd += ["-ss", f"{start:.2f}", "-t", f"{target_seconds:.2f}"]

    # Output: mono WAV, 44.1kHz
    cmd += ["-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(dst)]

    subprocess.run(cmd, capture_output=True, timeout=120)

    if not dst.exists():
        shutil.copy2(str(src), str(dst))


def _quick_quality_score(sample_path: Path) -> float:
    """Compute a 0-5 quality score. Longer samples score higher (60s ideal)."""
    try:
        import soundfile as sf
        data, sr = sf.read(str(sample_path))
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        duration = len(data) / sr
        rms = float(np.sqrt(np.mean(data ** 2)))
        score = 2.0
        # Duration: longer is better, 60s is ideal
        if duration >= 50:
            score += 1.5
        elif duration >= 30:
            score += 1.0
        elif duration >= 10:
            score += 0.5
        # Volume: good RMS
        if 0.01 < rms < 0.5:
            score += 0.5
        # Not clipping
        if float(np.abs(data).max()) < 0.95:
            score += 0.5
        # Sample rate
        if sr >= 16000:
            score += 0.5
        return min(5.0, round(score, 1))
    except Exception:
        return 2.5


def _detect_gender(filepath: Path) -> str:
    """Detect gender via pitch analysis. Handles any format via ffmpeg fallback."""
    try:
        import soundfile as sf
        try:
            data, sr = sf.read(str(filepath))
        except Exception:
            # soundfile can't read this format (e.g. OPUS) — decode via ffmpeg
            import subprocess, tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(filepath), "-t", "5", "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", tmp.name],
                capture_output=True, timeout=15,
            )
            data, sr = sf.read(tmp.name)
            Path(tmp.name).unlink(missing_ok=True)

        if len(data.shape) > 1:
            data = data.mean(axis=1)
        # Analyze a 1-second frame from the middle
        mid = len(data) // 2
        half_sec = sr // 2
        frame = data[max(0, mid - half_sec):mid + half_sec]
        if len(frame) < sr // 2:
            frame = data[:sr]
        # Autocorrelation pitch detection
        corr = np.correlate(frame, frame, 'full')
        corr = corr[len(corr) // 2:]
        min_lag = sr // 300
        max_lag = min(sr // 80, len(corr) - 1)
        search = corr[min_lag:max_lag]
        if len(search) > 0:
            peak_idx = int(np.argmax(search)) + min_lag
            f0 = sr / peak_idx
            return "Female" if f0 > 165 else "Male"
    except Exception:
        pass
    return "Male"


@router.post("/stage")
async def stage_upload(audio: UploadFile = File(...)):
    """Upload audio to staging. Survives page navigation. Returns a stage_id."""
    stage_id = str(uuid.uuid4())
    ext = audio.filename.rsplit(".", 1)[-1] if audio.filename else "wav"
    original_name = audio.filename or "audio.wav"
    dest = STAGING_DIR / f"{stage_id}.{ext}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    duration = _get_duration(dest)
    gender = _detect_gender(dest)

    return {
        "stage_id": stage_id,
        "filename": original_name,
        "ext": ext,
        "size": dest.stat().st_size,
        "duration": duration,
        "gender": gender,
        "audio_url": f"/audio/voices/staging/{stage_id}.{ext}",
    }


@router.get("/staged")
async def list_staged():
    """List all staged files with gender detection."""
    items = []
    for f in sorted(STAGING_DIR.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            stage_id = f.stem
            duration = _get_duration(f)
            gender = _detect_gender(f)
            items.append({
                "stage_id": stage_id,
                "filename": f.name,
                "ext": f.suffix.lstrip("."),
                "size": f.stat().st_size,
                "duration": duration,
                "gender": gender,
                "audio_url": f"/audio/voices/staging/{f.name}",
            })
    return items


@router.delete("/staged/{stage_id}")
async def delete_staged(stage_id: str):
    """Remove a staged file."""
    for f in STAGING_DIR.iterdir():
        if f.stem == stage_id:
            f.unlink()
            return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Staged file not found")


@router.post("/add-voices")
async def add_voices(
    voices: list[dict] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Add voices from staged files — no cloning, just saves audio + DB record."""
    results = []
    errors = []

    for v in voices:
        stage_id = v.get("stage_id")
        name = v.get("name", "Unnamed Voice")
        engine = v.get("engine", "chatterbox")
        language = v.get("language", "en")

        # Find staged file
        staged_file = None
        for f in STAGING_DIR.iterdir():
            if f.stem == stage_id:
                staged_file = f
                break

        if not staged_file:
            errors.append({"stage_id": stage_id, "name": name, "error": "Staged file not found"})
            continue

        try:
            sample_id = str(uuid.uuid4())
            sample_path = settings.samples_dir / f"{sample_id}.wav"

            # Convert to WAV + auto-trim center 25s via ffmpeg (single pass)
            _convert_and_trim(staged_file, sample_path, target_seconds=25)
            staged_file.unlink(missing_ok=True)

            # Compute quality score from the trimmed sample
            quality_score = _quick_quality_score(sample_path)

            # Create a placeholder embedding (will be computed on first use)
            embedding = np.zeros(256, dtype=np.float32)

            voice = await create_voice(
                session=session,
                name=name,
                engine=engine,
                language=language,
                tags=["imported"],
                notes="",
                embedding=embedding,
                sample_path=str(sample_path),
                quality_score=quality_score,
            )

            results.append({
                "stage_id": stage_id,
                "voice_id": voice.id,
                "name": voice.name,
                "quality_score": voice.quality_score,
            })
        except Exception as e:
            errors.append({"stage_id": stage_id, "name": name, "error": str(e)})

    return {"added": results, "errors": errors, "total": len(results), "failed": len(errors)}


# Keep legacy clone endpoint for backwards compat
@router.post("/create", response_model=VoiceResponse)
async def create_voice_clone(
    audio: UploadFile = File(...),
    name: str = Form(...),
    engine: str = Form("chatterbox"),
    language: str = Form("en"),
    tags: str = Form("[]"),
    notes: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    import json

    sample_id = str(uuid.uuid4())
    ext = audio.filename.rsplit(".", 1)[-1] if audio.filename else "wav"
    sample_path = settings.samples_dir / f"{sample_id}.{ext}"
    with open(sample_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    # Just create with placeholder embedding — no engine loading needed
    embedding = np.zeros(256, dtype=np.float32)
    quality_score = 2.5
    try:
        import soundfile as sf
        data, sr = sf.read(str(sample_path))
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        duration = len(data) / sr
        rms = float(np.sqrt(np.mean(data ** 2)))
        score = 2.5
        if 5 <= duration <= 15:
            score += 1.0
        elif 3 <= duration <= 30:
            score += 0.5
        if 0.01 < rms < 0.5:
            score += 0.5
        if float(np.abs(data).max()) < 0.95:
            score += 0.5
        if sr >= 16000:
            score += 0.5
        quality_score = min(5.0, round(score, 1))
    except Exception:
        pass

    tags_list = json.loads(tags) if isinstance(tags, str) else tags

    voice = await create_voice(
        session=session,
        name=name,
        engine=engine,
        language=language,
        tags=tags_list,
        notes=notes,
        embedding=embedding,
        sample_path=str(sample_path),
        quality_score=quality_score,
    )

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
        sample_url=f"/audio/voices/samples/{sample_path.name}",
        created_at=voice.created_at,
    )
