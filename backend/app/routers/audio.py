from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.schemas import AudioExportRequest, AudioMergeRequest
from app.services.audio_exporter import export_audio, merge_audio_files
from app.services.audio_processor import clean_audio

import uuid

import numpy as np
import soundfile as sf

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/export")
async def export_audio_endpoint(req: AudioExportRequest):
    source = Path(req.audio_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Source audio not found")

    audio, sr = sf.read(str(source))
    output_id = str(uuid.uuid4())
    output_path = settings.exports_dir / f"{output_id}.{req.format}"
    await export_audio(audio, req.sample_rate, output_path, format=req.format, bitrate=req.bitrate)

    return {"audio_url": f"/audio/exports/{output_path.name}", "format": req.format}


@router.post("/merge")
async def merge_audio_endpoint(req: AudioMergeRequest):
    paths = [Path(p) for p in req.audio_paths]
    for p in paths:
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Audio file not found: {p.name}")

    output_id = str(uuid.uuid4())
    output_path = settings.exports_dir / f"{output_id}.{req.output_format}"
    await merge_audio_files(paths, output_path, crossfade_ms=req.crossfade_ms)

    return {"audio_url": f"/audio/exports/{output_path.name}"}


@router.post("/convert")
async def convert_audio_format(req: dict):
    """Convert a WAV audio file to MP3, ACX MP3, or LPF format."""
    from pydub import AudioSegment
    from app.services.audio_processor import acx_normalize

    source_url = req.get("audio_url", "")
    target_format = req.get("format", "mp3")

    # Resolve source path from URL
    if source_url.startswith("/audio/temp/"):
        source = settings.temp_dir / source_url.split("/audio/temp/")[-1]
    elif source_url.startswith("/audio/exports/"):
        source = settings.exports_dir / source_url.split("/audio/exports/")[-1]
    else:
        raise HTTPException(status_code=400, detail="Invalid audio URL")

    if not source.exists():
        raise HTTPException(status_code=404, detail="Source audio not found")

    file_id = str(uuid.uuid4())

    if target_format == "mp3-acx":
        # Full ACX compliance
        segment = AudioSegment.from_file(str(source))
        samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
        samples = samples / (2 ** (segment.sample_width * 8 - 1))
        sr = segment.frame_rate

        if sr != 44100:
            from app.services.audio_processor import resample
            samples = resample(samples, sr, 44100)
            sr = 44100

        samples = acx_normalize(samples, sr)
        samples_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
        acx_segment = AudioSegment(
            data=samples_int16.tobytes(),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )
        output_path = settings.exports_dir / f"{file_id}.mp3"
        acx_segment.export(str(output_path), format="mp3", bitrate="192k",
                           parameters=["-ar", "44100", "-ac", "1"])
        return {"audio_url": f"/audio/exports/{output_path.name}", "format": "mp3-acx",
                "filename": f"frenzai_acx_{file_id[:8]}.mp3"}

    elif target_format == "mp3":
        segment = AudioSegment.from_file(str(source))
        output_path = settings.exports_dir / f"{file_id}.mp3"
        segment.export(str(output_path), format="mp3", bitrate="192k")
        return {"audio_url": f"/audio/exports/{output_path.name}", "format": "mp3",
                "filename": f"frenzai_{file_id[:8]}.mp3"}

    elif target_format == "lpf":
        segment = AudioSegment.from_file(str(source))
        output_path = settings.exports_dir / f"{file_id}.lpf"
        # LPF is MP3 internally
        temp_mp3 = settings.exports_dir / f"{file_id}.mp3"
        segment.export(str(temp_mp3), format="mp3", bitrate="192k")
        temp_mp3.rename(output_path)
        return {"audio_url": f"/audio/exports/{output_path.name}", "format": "lpf",
                "filename": f"frenzai_{file_id[:8]}.lpf"}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {target_format}")


@router.post("/extract-segment")
async def extract_segment(req: dict):
    """Extract a segment from a long audio file. For trimming 2+ hour files."""
    from pydub import AudioSegment

    audio_url = req.get("audio_url", "")
    start_sec = req.get("start", 0)
    end_sec = req.get("end", 30)

    # Resolve source path
    if audio_url.startswith("/audio/"):
        parts = audio_url.split("/audio/", 1)[-1]
        source = settings.data_dir / parts
    else:
        raise HTTPException(status_code=400, detail="Invalid audio URL")

    if not source.exists():
        raise HTTPException(status_code=404, detail="Audio not found")

    # Extract segment
    audio = AudioSegment.from_file(str(source))
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000)
    segment = audio[start_ms:end_ms]

    # Export
    file_id = str(uuid.uuid4())
    output_path = settings.temp_dir / f"segment_{file_id}.wav"
    segment.export(str(output_path), format="wav")

    return {
        "audio_url": f"/audio/temp/segment_{file_id}.wav",
        "duration": round(len(segment) / 1000, 2),
        "start": start_sec,
        "end": end_sec,
    }


@router.post("/upload-long")
async def upload_long_audio(file: UploadFile = File(...)):
    """Upload a long audio file (up to 2GB / 5hrs). Returns metadata + waveform peaks for fast rendering."""
    from pydub import AudioSegment
    import aiofiles

    # Stream to disk in chunks (handles 2GB+ files without loading into RAM)
    file_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "mp3"
    upload_path = settings.temp_dir / f"long_{file_id}.{ext}"

    total_bytes = 0
    async with aiofiles.open(str(upload_path), "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            await f.write(chunk)
            total_bytes += len(chunk)

    # Get duration without fully decoding
    try:
        audio = AudioSegment.from_file(str(upload_path))
        duration = len(audio) / 1000.0
        channels = audio.channels
        sr = audio.frame_rate

        # Generate low-res waveform peaks (500 points max for fast rendering)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        if channels > 1:
            samples = samples[::channels]  # Take first channel
        # Downsample to 500 peaks
        num_peaks = min(500, len(samples))
        chunk_size = max(1, len(samples) // num_peaks)
        peaks = []
        for i in range(0, len(samples), chunk_size):
            chunk = samples[i:i + chunk_size]
            peaks.append(float(np.abs(chunk).max()))
        # Normalize peaks to 0-1
        max_peak = max(peaks) if peaks else 1
        peaks = [p / max_peak for p in peaks]

    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to read audio: {e}")

    audio_url = f"/audio/temp/long_{file_id}.{ext}"

    return {
        "audio_url": audio_url,
        "duration": round(duration, 2),
        "sample_rate": sr,
        "channels": channels,
        "file_size_mb": round(total_bytes / 1024 / 1024, 1),
        "peaks": peaks,
    }


@router.post("/clean")
async def clean_audio_endpoint(audio_path: str):
    source = Path(audio_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Audio not found")

    audio, sr = sf.read(str(source))
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
    cleaned = await clean_audio(audio, sr)

    output_id = str(uuid.uuid4())
    output_path = settings.temp_dir / f"{output_id}_clean.wav"
    sf.write(str(output_path), cleaned, sr)

    return {"audio_url": f"/audio/temp/{output_path.name}"}
