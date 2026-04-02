import asyncio
from pathlib import Path

import numpy as np
import soundfile as sf


async def export_audio(
    audio: np.ndarray,
    sample_rate: int,
    output_path: Path,
    format: str = "wav",
    bitrate: str = "320k",
) -> Path:
    """Export audio array to file in specified format."""

    def _export():
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "wav":
            sf.write(str(output_path), audio, sample_rate, subtype="PCM_24")
        elif format == "flac":
            sf.write(str(output_path), audio, sample_rate, format="FLAC")
        elif format == "mp3":
            # Write WAV first, then convert via pydub
            temp_wav = output_path.with_suffix(".tmp.wav")
            sf.write(str(temp_wav), audio, sample_rate)
            try:
                from pydub import AudioSegment
                sound = AudioSegment.from_wav(str(temp_wav))
                sound.export(str(output_path), format="mp3", bitrate=bitrate)
            finally:
                temp_wav.unlink(missing_ok=True)
        else:
            sf.write(str(output_path), audio, sample_rate)
        return output_path

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _export)


async def merge_audio_files(
    audio_paths: list[Path],
    output_path: Path,
    crossfade_ms: int = 0,
) -> Path:
    """Merge multiple audio files into one."""

    def _merge():
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for path in audio_paths:
            segment = AudioSegment.from_file(str(path))
            if crossfade_ms > 0 and len(combined) > 0:
                combined = combined.append(segment, crossfade=crossfade_ms)
            else:
                combined += segment
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.export(str(output_path), format=output_path.suffix.lstrip("."))
        return output_path

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _merge)
