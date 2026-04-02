"""Audiobook generation service — generates audio chapter by chapter."""
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

import numpy as np

from app.config import settings
from app.engines.registry import engine_registry
from app.services.audio_exporter import export_audio
from app.services.audio_processor import acx_normalize, clean_audio, trim_silence


async def generate_chapter_audio(
    text: str,
    engine_name: str,
    voice_embedding: Optional[np.ndarray] = None,
    sample_path: Optional[str] = None,
    language: str = "en",
    speed: float = 1.0,
    kokoro_voice: Optional[str] = None,
) -> tuple[str, float]:
    """Generate audio for a chapter. Returns (audio_path, duration)."""
    engine = await engine_registry.get(engine_name)

    kwargs = {}
    if sample_path:
        kwargs["sample_path"] = sample_path
    if kokoro_voice:
        kwargs["kokoro_voice"] = kokoro_voice

    audio, sr = await engine.generate(
        text=text,
        voice_embedding=voice_embedding,
        language=language,
        speed=speed,
        **kwargs,
    )

    # Post-process
    audio = trim_silence(audio, sr)
    # Only apply light cleaning for high-quality engines
    if engine_name in ("kokoro", "chatterbox"):
        from app.services.audio_processor import normalize
        audio = normalize(audio, target_db=-3.0)
    else:
        audio = await clean_audio(audio, sr)

    # Save
    file_id = str(uuid.uuid4())
    output_path = settings.temp_dir / f"{file_id}.wav"
    await export_audio(audio, sr, output_path)

    duration = len(audio) / sr
    return str(output_path), round(duration, 2)


async def merge_chapter_audio(
    audio_paths: list[str],
    output_format: str = "wav",
    gap_seconds: float = 2.0,
    acx_compliant: bool = False,
) -> str:
    """Merge multiple chapter audio files into one audiobook file."""
    from pydub import AudioSegment

    combined = AudioSegment.empty()
    silence_gap = AudioSegment.silent(duration=int(gap_seconds * 1000))

    for i, path in enumerate(audio_paths):
        if not Path(path).exists():
            continue
        segment = AudioSegment.from_file(path)
        if i > 0:
            combined += silence_gap
        combined += segment

    # Export
    file_id = str(uuid.uuid4())
    ext = output_format.lower()
    is_acx = ext == "mp3-acx" or acx_compliant
    is_lpf = ext == "lpf"

    if is_acx:
        ext = "mp3"
    elif is_lpf:
        ext = "mp3"  # LPF uses MP3 internally

    output_path = settings.exports_dir / f"audiobook_{file_id}.{ext}"

    if is_acx:
        # ACX compliance: convert to numpy, apply ACX normalization, export
        samples = np.array(combined.get_array_of_samples(), dtype=np.float32)
        samples = samples / (2 ** (combined.sample_width * 8 - 1))  # Normalize to -1..1
        sr = combined.frame_rate

        # Resample to 44100 Hz if needed (ACX requirement)
        if sr != 44100:
            from app.services.audio_processor import resample
            samples = resample(samples, sr, 44100)
            sr = 44100

        # Apply ACX normalization
        samples = acx_normalize(samples, sr)

        # Convert back to pydub AudioSegment for MP3 export
        samples_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
        acx_segment = AudioSegment(
            data=samples_int16.tobytes(),
            sample_width=2,
            frame_rate=44100,
            channels=1,
        )

        # ACX MP3 export: 192 kbps CBR, 44.1 kHz, mono
        acx_segment.export(
            str(output_path),
            format="mp3",
            bitrate="192k",
            parameters=["-ar", "44100", "-ac", "1"],
        )
    else:
        export_params = {}
        if ext == "mp3":
            export_params = {"format": "mp3", "bitrate": "192k"}
        elif ext == "wav":
            export_params = {"format": "wav"}
        else:
            export_params = {"format": ext}

        combined.export(str(output_path), **export_params)

    # If LPF format requested, rename to .lpf
    if is_lpf:
        lpf_path = output_path.with_suffix(".lpf")
        output_path.rename(lpf_path)
        output_path = lpf_path

    return str(output_path)


async def export_chapter_acx(audio_path: str, chapter_title: str) -> str:
    """Export a single chapter as ACX-compliant MP3."""
    from pydub import AudioSegment

    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    segment = AudioSegment.from_file(audio_path)

    # Convert to numpy for processing
    samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
    samples = samples / (2 ** (segment.sample_width * 8 - 1))
    sr = segment.frame_rate

    # Resample to 44.1 kHz
    if sr != 44100:
        from app.services.audio_processor import resample
        samples = resample(samples, sr, 44100)
        sr = 44100

    # ACX normalize
    samples = acx_normalize(samples, sr)

    # Convert back
    samples_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
    acx_segment = AudioSegment(
        data=samples_int16.tobytes(),
        sample_width=2,
        frame_rate=44100,
        channels=1,
    )

    # Export
    safe_title = "".join(c for c in chapter_title if c.isalnum() or c in " _-").strip()
    safe_title = safe_title.replace(" ", "_")[:50] or "chapter"
    file_id = str(uuid.uuid4())[:8]
    output_path = settings.exports_dir / f"{safe_title}_{file_id}.mp3"

    acx_segment.export(
        str(output_path),
        format="mp3",
        bitrate="192k",
        parameters=["-ar", "44100", "-ac", "1"],
    )

    return str(output_path)
