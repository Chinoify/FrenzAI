"""
FrenzAI ACX Professional Audio Pipeline

Complete audiobook mastering chain that transforms raw TTS output into
ACX-compliant, human-sounding audiobook audio.

Pipeline order:
1. text_preprocessor → cleaned, voice-ready script
2. ssml_injector → script with emotion/pause tags
3. [TTS generates raw audio]
4. silence_normalizer → consistent pauses
5. breath_inserter → natural breathing
6. humanizer → micro pitch/speed variations
7. add_warmth → EQ + subtle reverb
8. noise_scrubber → clean noise floor
9. acx_master → RMS/peak/noise compliance
10. acx_checker → pass/fail report
"""
import random
import re
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from app.config import settings


# =============================================================================
# 1. TEXT PREPROCESSOR — Rewrite manuscript for voice
# =============================================================================
def text_preprocessor(text: str) -> str:
    """Rewrite text to be voice-ready before TTS generation."""
    # Spell out numbers
    number_words = {
        '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
        '10': 'ten', '11': 'eleven', '12': 'twelve', '13': 'thirteen',
        '14': 'fourteen', '15': 'fifteen', '16': 'sixteen', '17': 'seventeen',
        '18': 'eighteen', '19': 'nineteen', '20': 'twenty',
    }
    for num, word in sorted(number_words.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf'\b{num}\b', word, text)

    # Expand common abbreviations
    abbrevs = {
        r'\bMr\.': 'Mister', r'\bMrs\.': 'Missus', r'\bDr\.': 'Doctor',
        r'\bSt\.': 'Saint', r'\bvs\.': 'versus', r'\betc\.': 'etcetera',
        r'\bFBI\b': 'F.B.I.', r'\bCIA\b': 'C.I.A.', r'\bNASA\b': 'NASA',
        r'\bUSA\b': 'U.S.A.', r'\bAM\b': 'A.M.', r'\bPM\b': 'P.M.',
    }
    for pattern, replacement in abbrevs.items():
        text = re.sub(pattern, replacement, text)

    # Replace em-dashes with commas for better phrasing
    text = text.replace('—', ', ')
    text = text.replace('–', ', ')

    # Add ellipses for dramatic effect at sentence boundaries with conjunctions
    text = re.sub(r'\. (And|But|Yet|So|Then) ', r'... \1 ', text)

    # Break very long sentences at natural breath points
    def break_long_sentence(match):
        sentence = match.group(0)
        if len(sentence) > 200:
            # Find a natural break point (comma, semicolon, conjunction)
            mid = len(sentence) // 2
            # Look for nearest comma or semicolon near the middle
            for offset in range(0, min(50, mid)):
                for pos in [mid + offset, mid - offset]:
                    if 0 < pos < len(sentence) and sentence[pos] in ',;':
                        return sentence[:pos + 1] + ' ' + sentence[pos + 1:].lstrip()
        return sentence

    text = re.sub(r'[^.!?]+[.!?]', break_long_sentence, text)

    # Money: $50 → fifty dollars
    def money_to_words(match):
        amount = match.group(1)
        try:
            val = int(amount)
            if val in number_words:
                return f"{number_words[str(val)]} dollars"
        except ValueError:
            pass
        return match.group(0)

    text = re.sub(r'\$(\d+)', money_to_words, text)

    return text.strip()


# =============================================================================
# 2. SSML INJECTOR — Add emotion and pause tags
# =============================================================================
def ssml_injector(text: str) -> str:
    """Inject pause hints using punctuation patterns.

    Note: Most local TTS models don't support full SSML.
    Instead, we use punctuation and spacing as 'stage directions'.
    """
    # After chapter headers — extra pause via ellipsis
    text = re.sub(r'(Chapter \d+[^\n]*)\n', r'\1\n\n... \n', text)

    # After question marks — slight pause
    text = re.sub(r'\?(\s+)([A-Z])', r'?...\1\2', text)

    # Suspense/emphasis words — add slight hesitation
    suspense_words = ['suddenly', 'silence', 'darkness', 'alone', 'never',
                      'dead', 'blood', 'scream', 'whisper', 'shadow']
    for word in suspense_words:
        # Add comma before for micro-pause
        text = re.sub(rf'\b({word})\b', rf', \1', text, flags=re.IGNORECASE)
        # Clean up double commas
        text = text.replace(', ,', ',')

    # Dialogue — no changes needed, TTS handles quotes naturally

    return text.strip()


# =============================================================================
# 3. SILENCE NORMALIZER — Consistent pauses
# =============================================================================
def silence_normalizer(
    audio: np.ndarray,
    sr: int,
    sentence_silence_ms: int = 400,
    paragraph_silence_ms: int = 800,
    max_silence_ms: int = 1500,
) -> np.ndarray:
    """Normalize silence durations for consistent pacing."""
    threshold = 0.005  # amplitude threshold for silence detection
    min_silence_samples = int(0.15 * sr)  # 150ms minimum to count as silence

    # Find silent regions
    is_silent = np.abs(audio) < threshold
    regions = []
    in_silence = False
    start = 0

    for i in range(len(audio)):
        if is_silent[i] and not in_silence:
            start = i
            in_silence = True
        elif not is_silent[i] and in_silence:
            if i - start >= min_silence_samples:
                regions.append((start, i))
            in_silence = False

    if not regions:
        return audio

    # Replace silence regions with normalized durations
    result = []
    prev_end = 0

    for silence_start, silence_end in regions:
        # Keep audio before this silence
        result.append(audio[prev_end:silence_start])

        duration_ms = (silence_end - silence_start) / sr * 1000

        if duration_ms > max_silence_ms:
            # Cap at max
            target_ms = paragraph_silence_ms
        elif duration_ms > paragraph_silence_ms * 0.7:
            # Likely a paragraph break
            target_ms = paragraph_silence_ms
        else:
            # Sentence break
            target_ms = sentence_silence_ms

        target_samples = int(target_ms / 1000 * sr)
        result.append(np.zeros(target_samples, dtype=np.float32))
        prev_end = silence_end

    # Append remaining audio
    result.append(audio[prev_end:])
    return np.concatenate(result)


# =============================================================================
# 4. BREATH INSERTER — Natural breathing sounds
# =============================================================================
def breath_inserter(
    audio: np.ndarray,
    sr: int,
    breath_probability: float = 0.4,
) -> np.ndarray:
    """Insert subtle breath-like sounds at natural pause points.

    Uses synthesized pink noise shaped like an inhale rather than
    requiring a separate breath audio sample.
    """
    # Generate a subtle breath sound (shaped pink noise)
    breath_duration = int(0.1 * sr)  # 100ms breath
    t = np.linspace(0, 1, breath_duration)

    # Shape: quick rise, slow fall (like an inhale)
    envelope = np.sin(t * np.pi) ** 0.5
    # Pink noise approximation
    noise = np.random.randn(breath_duration).astype(np.float32)
    # Low-pass filter via simple rolling average
    kernel_size = int(sr * 0.002)  # 2ms kernel
    if kernel_size > 1:
        noise = np.convolve(noise, np.ones(kernel_size) / kernel_size, mode='same')
    breath_base = noise * envelope * 0.015  # Very subtle

    # Find silence regions (potential breath insertion points)
    threshold = 0.005
    min_silence = int(0.2 * sr)  # At least 200ms silence
    is_silent = np.abs(audio) < threshold

    regions = []
    in_silence = False
    start = 0
    for i in range(len(audio)):
        if is_silent[i] and not in_silence:
            start = i
            in_silence = True
        elif not is_silent[i] and in_silence:
            if i - start >= min_silence:
                regions.append((start, i))
            in_silence = False

    if not regions:
        return audio

    # Insert breaths at random subset of silence points
    result = audio.copy()
    for silence_start, silence_end in regions:
        if random.random() > breath_probability:
            continue

        # Vary breath volume slightly (±3dB)
        volume_variation = 10 ** (random.uniform(-3, 0) / 20)
        breath = breath_base * volume_variation

        # Insert breath in the middle of the silence
        mid = (silence_start + silence_end) // 2
        insert_start = max(silence_start, mid - breath_duration // 2)
        insert_end = min(silence_end, insert_start + breath_duration)
        actual_len = insert_end - insert_start

        if actual_len > 0:
            result[insert_start:insert_end] += breath[:actual_len]

    return result


# =============================================================================
# 5. HUMANIZER — Micro pitch/speed variations
# =============================================================================
def humanizer(audio: np.ndarray, sr: int) -> np.ndarray:
    """Add tiny random imperfections to make speech sound more natural.

    Applies per-chunk speed and volume micro-variations.
    """
    from scipy import signal as scipy_signal

    # Split into ~2-second chunks
    chunk_size = int(2.0 * sr)
    chunks = []

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) < sr // 4:  # Skip very short tail chunks
            chunks.append(chunk)
            continue

        # 1. Tiny speed variation (±1.5%)
        speed_factor = random.uniform(0.985, 1.015)
        new_length = int(len(chunk) / speed_factor)
        if new_length > 0:
            chunk = scipy_signal.resample(chunk, new_length).astype(np.float32)

        # 2. Tiny volume variation (±1dB)
        vol_db = random.uniform(-1.0, 1.0)
        chunk = chunk * (10 ** (vol_db / 20))

        chunks.append(chunk)

    return np.concatenate(chunks)


# =============================================================================
# 6. AUDIO WARMTH — EQ + subtle reverb
# =============================================================================
def add_warmth(audio: np.ndarray, sr: int) -> np.ndarray:
    """Add subtle warmth using EQ and reverb via pedalboard."""
    try:
        from pedalboard import (
            Pedalboard, Reverb, LowShelfFilter, HighShelfFilter, Compressor
        )

        board = Pedalboard([
            Compressor(threshold_db=-20, ratio=2.0, attack_ms=10, release_ms=100),
            LowShelfFilter(cutoff_frequency_hz=200, gain_db=1.5),
            HighShelfFilter(cutoff_frequency_hz=12000, gain_db=-2.0),
            Reverb(room_size=0.1, wet_level=0.05, dry_level=0.95),
        ])

        # pedalboard expects (channels, samples)
        if audio.ndim == 1:
            audio_2d = audio.reshape(1, -1)
        else:
            audio_2d = audio

        processed = board(audio_2d.astype(np.float32), sr)

        if processed.ndim > 1:
            processed = processed.squeeze()

        return processed.astype(np.float32)

    except ImportError:
        # Fallback: just apply simple high-frequency rolloff
        from scipy.signal import butter, filtfilt
        b, a = butter(2, 12000 / (sr / 2), btype='low')
        return filtfilt(b, a, audio).astype(np.float32)


# =============================================================================
# 7. NOISE SCRUBBER — Spectral denoising
# =============================================================================
def noise_scrubber(audio: np.ndarray, sr: int) -> np.ndarray:
    """Reduce noise floor to below -65dB using spectral subtraction."""
    try:
        import noisereduce as nr

        # Use first 0.5 seconds as noise profile
        noise_sample_len = min(int(0.5 * sr), len(audio) // 4)
        noise_sample = audio[:noise_sample_len]

        cleaned = nr.reduce_noise(
            y=audio, sr=sr,
            y_noise=noise_sample,
            prop_decrease=0.75,  # Don't over-process
        )
        return cleaned.astype(np.float32)
    except ImportError:
        return audio


# =============================================================================
# 8. ACX MASTERING — Professional loudness/peak compliance
# =============================================================================
def acx_master(
    audio: np.ndarray,
    sr: int,
    target_lufs: float = -20.0,
    peak_limit_db: float = -3.0,
) -> np.ndarray:
    """Master audio to ACX specifications using LUFS measurement."""
    if len(audio) == 0:
        return audio

    # Ensure mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    try:
        import pyloudnorm as pyln

        # Step 1: Measure current loudness (LUFS — industry standard)
        meter = pyln.Meter(sr)
        # pyloudnorm needs minimum length
        if len(audio) / sr < 0.5:
            # Too short for LUFS — use RMS fallback
            rms = np.sqrt(np.mean(audio ** 2))
            if rms > 0:
                rms_db = 20 * np.log10(rms)
                gain = 10 ** ((target_lufs - rms_db) / 20)
                audio = audio * gain
        else:
            loudness = meter.integrated_loudness(audio)
            # Step 2: Normalize to target LUFS
            if not np.isinf(loudness) and not np.isnan(loudness):
                audio = pyln.normalize.loudness(audio, loudness, target_lufs)

    except ImportError:
        # Fallback: RMS-based normalization
        rms = np.sqrt(np.mean(audio ** 2))
        if rms > 0:
            rms_db = 20 * np.log10(rms)
            gain = 10 ** ((target_lufs - rms_db) / 20)
            audio = audio * gain

    # Step 3: True peak limiter at -3dB
    peak_limit = 10 ** (peak_limit_db / 20)  # ~0.708
    peak = np.abs(audio).max()
    if peak > peak_limit:
        audio = audio * (peak_limit / peak)

    # Step 4: Resample to 44.1kHz if needed
    if sr != 44100:
        from scipy.signal import resample
        new_len = int(len(audio) * 44100 / sr)
        audio = resample(audio, new_len).astype(np.float32)

    # Step 5: Silence padding (ACX: 0.5-1s start, 1-5s end)
    start_silence = np.zeros(int(0.75 * 44100), dtype=np.float32)
    end_silence = np.zeros(int(2.5 * 44100), dtype=np.float32)
    audio = np.concatenate([start_silence, audio, end_silence])

    return audio.astype(np.float32)


# =============================================================================
# 9. ACX COMPLIANCE CHECKER — QA gate
# =============================================================================
def acx_check(audio: np.ndarray, sr: int) -> dict:
    """Check if audio meets all ACX requirements. Returns detailed report."""
    report = {
        "overall": "PASS",
        "checks": {},
    }

    # Ensure mono for measurement
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # 1. RMS Level (-23 to -18 dB)
    # Measure only voiced portions
    voiced = audio[np.abs(audio) > 0.001]
    if len(voiced) > 0:
        rms = np.sqrt(np.mean(voiced ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
    else:
        rms_db = -100

    rms_pass = -23 <= rms_db <= -18
    report["checks"]["rms"] = {
        "value": round(rms_db, 1),
        "target": "-23 to -18 dB",
        "pass": rms_pass,
    }
    if not rms_pass:
        report["overall"] = "FAIL"

    # 2. True Peak (below -3dB)
    peak = np.abs(audio).max()
    peak_db = 20 * np.log10(peak + 1e-10)
    peak_pass = peak_db < -3.0
    report["checks"]["peak"] = {
        "value": round(peak_db, 1),
        "target": "below -3 dB",
        "pass": peak_pass,
    }
    if not peak_pass:
        report["overall"] = "FAIL"

    # 3. Noise Floor (below -60dB)
    # Measure the quietest 10% of audio
    sorted_abs = np.sort(np.abs(audio))
    noise_portion = sorted_abs[:len(sorted_abs) // 10]
    if len(noise_portion) > 0:
        noise_rms = np.sqrt(np.mean(noise_portion ** 2))
        noise_db = 20 * np.log10(noise_rms + 1e-10)
    else:
        noise_db = -100

    noise_pass = noise_db < -60
    report["checks"]["noise_floor"] = {
        "value": round(noise_db, 1),
        "target": "below -60 dB",
        "pass": noise_pass,
    }
    if not noise_pass:
        report["overall"] = "FAIL"

    # 4. Sample Rate
    sr_pass = sr == 44100
    report["checks"]["sample_rate"] = {
        "value": sr,
        "target": 44100,
        "pass": sr_pass,
    }
    if not sr_pass:
        report["overall"] = "FAIL"

    # 5. Duration check (max 120 minutes)
    duration_minutes = len(audio) / sr / 60
    duration_pass = duration_minutes <= 120
    report["checks"]["duration"] = {
        "value": round(duration_minutes, 1),
        "target": "max 120 minutes",
        "pass": duration_pass,
    }
    if not duration_pass:
        report["overall"] = "FAIL"

    # LUFS measurement if pyloudnorm available
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        if len(audio) / sr >= 0.5:
            lufs = meter.integrated_loudness(audio)
            report["checks"]["lufs"] = {
                "value": round(lufs, 1),
                "target": "-23 to -18 LUFS",
                "pass": -23 <= lufs <= -18,
            }
    except ImportError:
        pass

    return report


# =============================================================================
# 10. FULL PIPELINE — Run everything in order
# =============================================================================
def run_acx_pipeline(
    audio: np.ndarray,
    sr: int,
    enable_breaths: bool = True,
    enable_humanizer: bool = True,
    enable_warmth: bool = True,
    enable_noise_scrub: bool = True,
) -> tuple[np.ndarray, int, dict]:
    """Run the complete ACX humanization pipeline.

    Returns (processed_audio, sample_rate, acx_report).
    """
    print("[ACX Pipeline] Starting...")

    # Step 1: Silence normalization
    print("[ACX Pipeline] Normalizing silence...")
    audio = silence_normalizer(audio, sr)

    # Step 2: Breath insertion
    if enable_breaths:
        print("[ACX Pipeline] Inserting breaths...")
        audio = breath_inserter(audio, sr)

    # Step 3: Humanizer
    if enable_humanizer:
        print("[ACX Pipeline] Humanizing...")
        audio = humanizer(audio, sr)

    # Step 4: Warmth
    if enable_warmth:
        print("[ACX Pipeline] Adding warmth...")
        audio = add_warmth(audio, sr)

    # Step 5: Noise scrubber
    if enable_noise_scrub:
        print("[ACX Pipeline] Scrubbing noise...")
        audio = noise_scrubber(audio, sr)

    # Step 6: ACX mastering (loudness, peaks, silence padding)
    print("[ACX Pipeline] Mastering to ACX specs...")
    audio = acx_master(audio, sr)
    sr = 44100  # acx_master resamples to 44.1kHz

    # Step 7: Compliance check
    report = acx_check(audio, sr)
    print(f"[ACX Pipeline] Compliance: {report['overall']}")
    for name, check in report["checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        print(f"  {status} {name}: {check['value']} (target: {check['target']})")

    return audio, sr, report


# =============================================================================
# EXPORT — Save as ACX-compliant MP3
# =============================================================================
def export_acx_mp3(audio: np.ndarray, sr: int, output_path: str) -> str:
    """Export audio as ACX-compliant 192kbps CBR MP3."""
    # Save as WAV first
    wav_path = output_path.replace('.mp3', '.wav')
    sf.write(wav_path, audio, sr, subtype='PCM_16')

    # Convert to MP3 via ffmpeg
    mp3_path = output_path if output_path.endswith('.mp3') else output_path + '.mp3'

    ffmpeg_path = str(Path(settings.data_dir).parent / "ffmpeg.exe")
    if not Path(ffmpeg_path).exists():
        ffmpeg_path = "ffmpeg"

    subprocess.run([
        ffmpeg_path, '-y', '-i', wav_path,
        '-ar', '44100', '-ac', '1',
        '-b:a', '192k',
        '-write_xing', '0',  # CBR mode
        mp3_path,
    ], capture_output=True)

    # Clean up WAV
    Path(wav_path).unlink(missing_ok=True)
    return mp3_path


# =============================================================================
# CONSISTENCY ENGINE — Cross-chapter matching
# =============================================================================
class ConsistencyEngine:
    """Ensures all chapters sound like they came from the same session."""

    def __init__(self):
        self._reference_rms: Optional[float] = None
        self._reference_lufs: Optional[float] = None

    def set_reference(self, audio: np.ndarray, sr: int):
        """Set chapter 1 as the reference for all subsequent chapters."""
        voiced = audio[np.abs(audio) > 0.001]
        if len(voiced) > 0:
            self._reference_rms = np.sqrt(np.mean(voiced ** 2))

        try:
            import pyloudnorm as pyln
            meter = pyln.Meter(sr)
            if len(audio) / sr >= 0.5:
                self._reference_lufs = meter.integrated_loudness(audio)
        except ImportError:
            pass

    def match_to_reference(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Adjust audio to match the reference chapter's characteristics."""
        if self._reference_rms is None:
            return audio

        # Match RMS
        voiced = audio[np.abs(audio) > 0.001]
        if len(voiced) > 0:
            current_rms = np.sqrt(np.mean(voiced ** 2))
            if current_rms > 0:
                gain = self._reference_rms / current_rms
                # Limit gain to ±3dB to avoid over-correction
                max_gain = 10 ** (3 / 20)
                gain = np.clip(gain, 1 / max_gain, max_gain)
                audio = audio * gain

        return audio

    def check_consistency(self, audio: np.ndarray, sr: int) -> dict:
        """Check if this chapter matches the reference within 1dB."""
        if self._reference_rms is None:
            return {"consistent": True, "difference_db": 0}

        voiced = audio[np.abs(audio) > 0.001]
        if len(voiced) == 0:
            return {"consistent": True, "difference_db": 0}

        current_rms = np.sqrt(np.mean(voiced ** 2))
        ref_db = 20 * np.log10(self._reference_rms + 1e-10)
        cur_db = 20 * np.log10(current_rms + 1e-10)
        diff = abs(cur_db - ref_db)

        return {
            "consistent": diff <= 1.0,
            "difference_db": round(diff, 2),
            "reference_db": round(ref_db, 1),
            "chapter_db": round(cur_db, 1),
        }


# Global consistency engine instance
consistency_engine = ConsistencyEngine()
