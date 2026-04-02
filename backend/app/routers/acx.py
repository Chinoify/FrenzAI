"""ACX compliance API — check and master audio files."""
import uuid

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.acx_pipeline import acx_check, acx_master, run_acx_pipeline

router = APIRouter(prefix="/api/acx", tags=["acx"])


@router.post("/check")
async def check_compliance(file: UploadFile = File(...)):
    """Check if an audio file meets ACX requirements.

    Returns detailed pass/fail for each metric: RMS, peak, noise floor,
    sample rate, channels.
    """
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    upload_path = settings.temp_dir / f"acx_check_{upload_id}.{ext}"

    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)

        data, sr = sf.read(str(upload_path))
        if data.ndim > 1:
            data = data.mean(axis=1)

        report = acx_check(data, sr)
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ACX check failed: {e}")
    finally:
        upload_path.unlink(missing_ok=True)


@router.post("/master")
async def master_audio(
    file: UploadFile = File(...),
):
    """Run full ACX mastering pipeline on an audio file.

    Applies: noise scrub → warmth EQ → humanizer → ACX normalization.
    Returns before/after metrics and mastered audio URL.
    """
    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    upload_path = settings.temp_dir / f"acx_master_{upload_id}.{ext}"

    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)

        data, sr = sf.read(str(upload_path))
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Before metrics
        before = acx_check(data, sr)

        # Run pipeline
        processed, new_sr, after = run_acx_pipeline(data.astype(np.float32), sr)

        # Save
        output_path = settings.exports_dir / f"mastered_{upload_id}.wav"
        sf.write(str(output_path), processed, new_sr, subtype="PCM_16")

        return {
            "audio_url": f"/audio/exports/{output_path.name}",
            "before_metrics": before,
            "after_metrics": after,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mastering failed: {e}")
    finally:
        upload_path.unlink(missing_ok=True)
