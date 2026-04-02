import asyncio

import numpy as np
import noisereduce as nr
from scipy import signal


async def clean_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply noise reduction and normalization."""

    def _clean():
        cleaned = audio.copy()
        # Noise reduction
        try:
            cleaned = nr.reduce_noise(y=cleaned, sr=sample_rate, prop_decrease=0.6)
        except Exception:
            pass
        # Normalize
        cleaned = normalize(cleaned)
        return cleaned

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _clean)


def normalize(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """Normalize audio to target dB level."""
    peak = np.abs(audio).max()
    if peak == 0:
        return audio
    target_amplitude = 10 ** (target_db / 20.0)
    return audio * (target_amplitude / peak)


def trim_silence(audio: np.ndarray, sample_rate: int, threshold_db: float = -40.0) -> np.ndarray:
    """Trim leading and trailing silence."""
    threshold = 10 ** (threshold_db / 20.0)
    above = np.abs(audio) > threshold
    if not above.any():
        return audio
    first = np.argmax(above)
    last = len(above) - np.argmax(above[::-1])
    # Keep small padding
    pad = int(0.05 * sample_rate)
    first = max(0, first - pad)
    last = min(len(audio), last + pad)
    return audio[first:last]


def resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio to target sample rate."""
    if orig_sr == target_sr:
        return audio
    num_samples = int(len(audio) * target_sr / orig_sr)
    return signal.resample(audio, num_samples).astype(np.float32)


def acx_normalize(audio: np.ndarray, sample_rate: int, skip_noise_reduction: bool = True) -> np.ndarray:
    """Apply ACX audiobook standard normalization.

    ACX Requirements:
    - Peak values: max -3dB
    - RMS (average loudness): -23dB to -18dB (target: -20dB)
    - Noise floor: below -60dB
    - 0.5-1s silence at start, 1-5s silence at end

    skip_noise_reduction: Skip slow noisereduce for already-clean TTS audio (Kokoro etc).
    """
    if len(audio) == 0:
        return audio

    # Step 1: Noise floor handling
    # For TTS-generated audio (Kokoro, etc), skip the expensive noisereduce.
    # Instead use a fast noise gate — zero out samples below -60dB threshold.
    if skip_noise_reduction:
        noise_threshold = 10 ** (-60.0 / 20.0)  # -60dB
        audio = np.where(np.abs(audio) < noise_threshold, 0.0, audio)
    else:
        try:
            audio = nr.reduce_noise(y=audio, sr=sample_rate, prop_decrease=0.8)
        except Exception:
            pass

    # Step 2: Compute current RMS
    # Only measure RMS on non-silent parts for accuracy
    voiced = audio[np.abs(audio) > 1e-6]
    rms = np.sqrt(np.mean(voiced ** 2)) if len(voiced) > 0 else 0
    if rms == 0:
        return audio

    rms_db = 20 * np.log10(rms + 1e-10)

    # Step 3: Target RMS of -20dB (middle of -23 to -18 range)
    target_rms_db = -20.0
    gain_db = target_rms_db - rms_db
    gain = 10 ** (gain_db / 20.0)
    audio = audio * gain

    # Step 4: Apply limiter — hard limit peaks to -3dB
    peak_limit = 10 ** (-3.0 / 20.0)  # ~0.708
    peak = np.abs(audio).max()
    if peak > peak_limit:
        ratio = peak_limit / peak
        audio = audio * ratio

    # Step 5: Add silence padding
    # 0.75s at start, 2.5s at end (within ACX range)
    start_silence = np.zeros(int(0.75 * sample_rate), dtype=np.float32)
    end_silence = np.zeros(int(2.5 * sample_rate), dtype=np.float32)
    audio = np.concatenate([start_silence, audio, end_silence])

    return audio.astype(np.float32)
