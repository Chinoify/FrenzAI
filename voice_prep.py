"""
voice_prep.py
=============
Prepares any audio recording as a reference voice WAV for TTS cloning.
- Validates duration (warns if too short or too long)
- Converts to mono
- Resamples to 24kHz (Pocket TTS native)
- Normalizes volume
- Trims leading/trailing silence
- Saves a clean _prepped.wav alongside the original

Usage:
    python voice_prep.py --input my_recording.wav
    python voice_prep.py --input my_recording.mp3   # needs ffmpeg

Requirements:
    pip install soundfile scipy numpy
    (For MP3 input: also install ffmpeg system tool)
"""

import argparse
import os
import sys
import subprocess
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as sig
import soundfile as sf
from pathlib import Path

TARGET_SR   = 24000
MIN_SEC     = 5.0
MAX_SEC     = 30.0
TRIM_THRESH = 0.01    # amplitude below this is considered silence


def convert_to_wav(input_path: str) -> str:
    """Use ffmpeg to convert non-WAV to WAV."""
    out = input_path.rsplit(".", 1)[0] + "_converted.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "24000", "-ac", "1", out],
            check=True, capture_output=True,
        )
        return out
    except FileNotFoundError:
        sys.exit("ERROR: ffmpeg not found. Install it or provide a .wav file directly.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: ffmpeg conversion failed:\n{e.stderr.decode()}")


def trim_silence(audio: np.ndarray, threshold: float = TRIM_THRESH) -> np.ndarray:
    """Remove leading and trailing silence."""
    above = np.where(np.abs(audio) > threshold)[0]
    if len(above) == 0:
        return audio
    return audio[above[0]:above[-1] + 1]


def prep_voice(input_path: str) -> str:
    p = Path(input_path)

    # Convert non-WAV formats
    if p.suffix.lower() != ".wav":
        print(f"Converting {p.suffix} → WAV via ffmpeg...")
        input_path = convert_to_wav(input_path)
        p = Path(input_path)

    # Load
    audio, sr = sf.read(input_path, dtype="float32", always_2d=False)
    print(f"Loaded: {input_path}")
    print(f"  Sample rate : {sr} Hz")
    print(f"  Channels    : {'stereo' if audio.ndim == 2 else 'mono'}")
    print(f"  Duration    : {len(audio)/sr:.2f}s")

    # Convert stereo → mono
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
        print("  → Converted to mono")

    # Resample to 24kHz
    if sr != TARGET_SR:
        n = int(len(audio) * TARGET_SR / sr)
        audio = sig.resample(audio, n).astype(np.float32)
        print(f"  → Resampled to {TARGET_SR} Hz")

    # Trim silence
    audio = trim_silence(audio)
    duration = len(audio) / TARGET_SR

    # Normalize to -18 dBFS RMS
    rms = np.sqrt(np.mean(audio ** 2))
    if rms > 1e-10:
        target_rms = 10 ** (-18 / 20)
        audio = audio * (target_rms / rms)
        peak = np.max(np.abs(audio))
        if peak > 0.95:
            audio = audio * (0.95 / peak)

    # Duration checks
    print(f"\n  ✔ Cleaned duration: {duration:.2f}s")
    if duration < MIN_SEC:
        print(f"  ⚠ WARNING: {duration:.1f}s is shorter than the {MIN_SEC}s minimum.")
        print("    Pocket TTS will still clone but quality may be lower.")
        print("    Tip: Use a clean, expressive 10–20 second recording for best results.")
    elif duration > MAX_SEC:
        print(f"  ⚠ NOTE: {duration:.1f}s — trimming to {MAX_SEC}s (Pocket TTS only uses first ~20s).")
        audio = audio[:int(MAX_SEC * TARGET_SR)]
    else:
        print(f"  ✅ Duration is ideal ({MIN_SEC}–{MAX_SEC}s range).")

    # Save
    out_path = str(p.parent / (p.stem + "_prepped.wav"))
    audio_int16 = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_int16 * 32767).astype(np.int16)
    wavfile.write(out_path, TARGET_SR, audio_int16)

    print(f"\n  ✅ Saved prepped voice: {out_path}")
    print(f"  Use this file as your --voice argument in audiobook_pocket_tts.py")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare reference voice WAV for Pocket TTS")
    parser.add_argument("--input", required=True, help="Input audio file (.wav, .mp3, .m4a, .flac)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"ERROR: File not found: {args.input}")

    prep_voice(args.input)
