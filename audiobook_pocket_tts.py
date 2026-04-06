"""
audiobook_pocket_tts.py
=======================
Batch audiobook generator using Pocket TTS (Kyutai).
- Clones a voice from a short WAV reference file (5-20 sec ideal)
- Splits manuscript text into chapters automatically
- Generates per-chapter WAV files
- Optionally concatenates into a single audiobook WAV
- ACX-compatible output (24kHz mono, normalized)
- Integrates with your existing audiobook_master.py standards

Usage:
    python audiobook_pocket_tts.py \
        --text manuscript.txt \
        --voice my_narrator_voice.wav \
        --output_dir ./audiobook_output \
        --title "My Book Title" \
        --pen_name "Grace Ifeoma Ezedinma"

Requirements:
    pip install pocket-tts scipy soundfile numpy tqdm
"""

import argparse
import os
import sys
import re
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# ── Third-party (install once) ────────────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    sys.exit("ERROR: numpy not found. Run: pip install numpy")

try:
    import scipy.io.wavfile as wavfile
    import scipy.signal as signal
except ImportError:
    sys.exit("ERROR: scipy not found. Run: pip install scipy")

try:
    import soundfile as sf
except ImportError:
    sys.exit("ERROR: soundfile not found. Run: pip install soundfile")

try:
    from tqdm import tqdm
except ImportError:
    # Graceful fallback if tqdm not installed
    def tqdm(iterable, **kwargs):
        desc = kwargs.get("desc", "")
        total = kwargs.get("total", None)
        for i, item in enumerate(iterable):
            print(f"\r{desc}: {i+1}/{total or '?'}", end="", flush=True)
            yield item
        print()

# ── Pocket TTS ────────────────────────────────────────────────────────────────
try:
    from pocket_tts import TTSModel
    POCKET_TTS_AVAILABLE = True
except ImportError:
    POCKET_TTS_AVAILABLE = False

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

CHAPTER_PATTERNS = [
    r"^\s*Chapter\s+\d+",                    # Chapter 1, Chapter 12
    r"^\s*CHAPTER\s+\d+",                    # CHAPTER 1
    r"^\s*Chapter\s+[A-Za-z]+",              # Chapter One, Chapter Two
    r"^\s*Part\s+\d+",                       # Part 1
    r"^\s*PART\s+\d+",
    r"^\s*Prologue\b",
    r"^\s*Epilogue\b",
    r"^\s*Introduction\b",
    r"^\s*\d+\.\s+[A-Z]",                    # 1. The Beginning
    r"^\s*---+\s*$",                          # separator lines
    r"^\s*\*\*\*+\s*$",
]

CHAPTER_RE = re.compile("|".join(CHAPTER_PATTERNS), re.MULTILINE | re.IGNORECASE)

# Max chars per TTS chunk — Pocket TTS works best under ~400 chars per call
CHUNK_SIZE = 350


def load_text(path: str) -> str:
    """Load manuscript from .txt or .md file."""
    p = Path(path)
    if not p.exists():
        sys.exit(f"ERROR: Text file not found: {path}")
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    for enc in encodings:
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    sys.exit(f"ERROR: Could not decode {path}. Save it as UTF-8.")


def split_into_chapters(text: str) -> list[dict]:
    """
    Split raw manuscript text into a list of chapter dicts:
        {"title": str, "body": str, "index": int}
    Falls back to one chapter if no markers found.
    """
    splits = list(CHAPTER_RE.finditer(text))

    if not splits:
        log.warning("No chapter markers detected — treating entire manuscript as one chapter.")
        return [{"title": "Full Book", "body": text.strip(), "index": 1}]

    chapters = []
    for i, match in enumerate(splits):
        start = match.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        raw = text[start:end].strip()
        # First line = title
        lines = raw.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if body:
            chapters.append({"title": title, "body": body, "index": i + 1})

    log.info(f"Found {len(chapters)} chapter(s).")
    return chapters


def clean_text(text: str) -> str:
    """
    Normalise text for TTS:
    - Remove markdown formatting
    - Expand common abbreviations
    - Remove excessive whitespace
    """
    # Strip markdown headers and emphasis
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    # Remove markdown links
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Straighten quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Em/en dashes → comma or pause
    text = text.replace("\u2014", " — ").replace("\u2013", " - ")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """
    Split text into chunks of ≤max_chars, breaking on sentence boundaries.
    Pocket TTS produces better results on sentence-level chunks.
    """
    # Split on sentence-ending punctuation
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # If a single sentence exceeds max_chars, break on comma or mid-word
        if len(sentence) > max_chars:
            sub_parts = re.split(r"(?<=,)\s+", sentence)
            for part in sub_parts:
                if len(current) + len(part) + 1 <= max_chars:
                    current = (current + " " + part).strip()
                else:
                    if current:
                        chunks.append(current)
                    # Hard split if even comma chunks are too long
                    while len(part) > max_chars:
                        chunks.append(part[:max_chars])
                        part = part[max_chars:]
                    current = part
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO PROCESSING  (ACX / Audible standards)
# ═══════════════════════════════════════════════════════════════════════════════

TARGET_SAMPLE_RATE = 24000   # Pocket TTS native
ACX_SAMPLE_RATE    = 44100   # ACX requirement for final delivery
ACX_PEAK_DB        = -3.0    # ACX peak ceiling
ACX_RMS_DB         = -20.0   # ACX RMS target (range: -23 to -18 dBFS)
CHAPTER_PAUSE_SEC  = 2.0     # Silence gap between chapters


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def linear_to_db(amp: float) -> float:
    return 20 * np.log10(max(amp, 1e-10))


def normalize_audio(audio: np.ndarray, target_rms_db: float = ACX_RMS_DB,
                    peak_ceiling_db: float = ACX_PEAK_DB) -> np.ndarray:
    """Normalize audio to ACX RMS target with peak ceiling."""
    audio = audio.astype(np.float32)

    # RMS calculation
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < 1e-10:
        return audio  # silence — skip

    current_rms_db = linear_to_db(rms)
    gain_db = target_rms_db - current_rms_db
    gain = db_to_linear(gain_db)
    audio = audio * gain

    # Peak ceiling enforcement
    peak = np.max(np.abs(audio))
    ceiling = db_to_linear(peak_ceiling_db)
    if peak > ceiling:
        audio = audio * (ceiling / peak)

    return audio


def resample_audio(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample using scipy polyphase filter."""
    if src_rate == dst_rate:
        return audio
    ratio = dst_rate / src_rate
    n_samples = int(len(audio) * ratio)
    return signal.resample(audio, n_samples).astype(np.float32)


def make_silence(duration_sec: float, sample_rate: int) -> np.ndarray:
    return np.zeros(int(duration_sec * sample_rate), dtype=np.float32)


def save_wav(path: str, audio: np.ndarray, sample_rate: int):
    """Save float32 audio as 16-bit WAV."""
    audio_int16 = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio_int16 * 32767).astype(np.int16)
    wavfile.write(path, sample_rate, audio_int16)


def concat_wavs(wav_paths: list[str], output_path: str,
                pause_sec: float = CHAPTER_PAUSE_SEC,
                target_sr: int = ACX_SAMPLE_RATE):
    """Concatenate chapter WAV files with silence gaps → single audiobook file."""
    segments = []
    pause = make_silence(pause_sec, target_sr)

    for i, p in enumerate(wav_paths):
        data, sr = sf.read(p, dtype="float32")
        if sr != target_sr:
            data = resample_audio(data, sr, target_sr)
        segments.append(data)
        if i < len(wav_paths) - 1:
            segments.append(pause)

    combined = np.concatenate(segments)
    combined = normalize_audio(combined)
    save_wav(output_path, combined, target_sr)
    return combined


# ═══════════════════════════════════════════════════════════════════════════════
# POCKET TTS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PocketTTSEngine:
    """Wrapper around Pocket TTS with voice state management."""

    def __init__(self, voice_ref: str):
        if not POCKET_TTS_AVAILABLE:
            sys.exit(
                "ERROR: pocket-tts not installed.\n"
                "Run: pip install pocket-tts\n"
                "Requires PyTorch 2.5+ (CPU version is fine):\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu"
            )
        log.info("Loading Pocket TTS model (first load takes ~30 sec)...")
        self.model = TTSModel.load_model()
        log.info(f"Loading voice reference: {voice_ref}")
        self.voice_state = self.model.get_state_for_audio_prompt(voice_ref)
        self.sample_rate = self.model.sample_rate
        log.info(f"Voice cloned. Sample rate: {self.sample_rate} Hz")

    def synthesize(self, text: str) -> np.ndarray:
        """Synthesize a single text chunk. Returns float32 numpy array."""
        audio_tensor = self.model.generate_audio(self.voice_state, text)
        return audio_tensor.numpy().astype(np.float32)

    def synthesize_chunks(self, chunks: list[str],
                          pause_between: float = 0.3) -> np.ndarray:
        """Synthesize a list of chunks and join with short pauses."""
        segments = []
        pause = make_silence(pause_between, self.sample_rate)
        for chunk in chunks:
            audio = self.synthesize(chunk)
            segments.append(audio)
            segments.append(pause)
        return np.concatenate(segments) if segments else np.array([], dtype=np.float32)


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS / STATE (resume on crash)
# ═══════════════════════════════════════════════════════════════════════════════

def load_progress(progress_file: str) -> set:
    """Return set of already-completed chapter indices."""
    if not os.path.exists(progress_file):
        return set()
    try:
        with open(progress_file) as f:
            data = json.load(f)
        return set(data.get("completed", []))
    except Exception:
        return set()


def save_progress(progress_file: str, completed: set):
    with open(progress_file, "w") as f:
        json.dump({"completed": sorted(completed), "updated": datetime.now().isoformat()}, f)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run(args):
    # ── Setup output directory ──────────────────────────────────────────────
    out_dir = Path(args.output_dir)
    chapters_dir = out_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    progress_file = str(out_dir / "progress.json")
    completed = load_progress(progress_file)

    # ── Load & parse manuscript ─────────────────────────────────────────────
    log.info(f"Loading manuscript: {args.text}")
    raw_text = load_text(args.text)
    chapters = split_into_chapters(raw_text)

    log.info(f"Book: '{args.title}' by {args.pen_name}")
    log.info(f"Total chapters: {len(chapters)}")

    # ── Load TTS engine ─────────────────────────────────────────────────────
    engine = PocketTTSEngine(voice_ref=args.voice)

    # ── Per-chapter generation ──────────────────────────────────────────────
    chapter_wavs = []
    total_chars = 0
    start_time = time.time()

    for ch in tqdm(chapters, desc="Generating chapters", total=len(chapters)):
        idx = ch["index"]
        safe_title = re.sub(r"[^\w\s-]", "", ch["title"])[:40].strip().replace(" ", "_")
        out_file = str(chapters_dir / f"ch{idx:03d}_{safe_title}.wav")
        chapter_wavs.append(out_file)

        if idx in completed:
            log.info(f"  ↳ Chapter {idx} already done — skipping.")
            continue

        log.info(f"  ▶ Chapter {idx}: {ch['title']} ({len(ch['body'])} chars)")

        # Clean and chunk the chapter body
        cleaned = clean_text(ch["body"])
        chunks = chunk_text(cleaned, max_chars=args.chunk_size)
        total_chars += len(cleaned)

        if not chunks:
            log.warning(f"  Chapter {idx} has no usable text — skipping.")
            completed.add(idx)
            save_progress(progress_file, completed)
            continue

        # Generate audio
        chapter_audio = engine.synthesize_chunks(chunks, pause_between=0.25)

        # Normalize to ACX standards at Pocket TTS sample rate
        chapter_audio = normalize_audio(chapter_audio, ACX_RMS_DB, ACX_PEAK_DB)

        # Upsample to ACX required 44.1kHz
        chapter_audio_44k = resample_audio(chapter_audio, engine.sample_rate, ACX_SAMPLE_RATE)

        # Save chapter WAV
        save_wav(out_file, chapter_audio_44k, ACX_SAMPLE_RATE)

        duration_sec = len(chapter_audio) / engine.sample_rate
        log.info(f"  ✓ Saved: {out_file} ({duration_sec:.1f}s audio, {len(chunks)} chunks)")

        completed.add(idx)
        save_progress(progress_file, completed)

    # ── Concatenate into full audiobook ─────────────────────────────────────
    existing_wavs = [p for p in chapter_wavs if os.path.exists(p)]

    if args.concat and existing_wavs:
        safe_book = re.sub(r"[^\w\s-]", "", args.title)[:50].strip().replace(" ", "_")
        full_output = str(out_dir / f"{safe_book}_FULL_AUDIOBOOK.wav")
        log.info(f"Concatenating {len(existing_wavs)} chapters → {full_output}")
        concat_wavs(existing_wavs, full_output, pause_sec=args.chapter_pause)
        full_size_mb = os.path.getsize(full_output) / (1024 * 1024)
        log.info(f"✅ Full audiobook saved: {full_output} ({full_size_mb:.1f} MB)")

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    log.info("─" * 55)
    log.info(f"DONE  |  {len(completed)} chapters  |  {total_chars:,} chars  |  {elapsed:.1f}s elapsed")
    log.info(f"Output directory: {out_dir.resolve()}")
    log.info("─" * 55)

    # Print ACX compliance reminder
    print("\n📋 ACX Compliance Checklist:")
    print(f"  Sample rate : {ACX_SAMPLE_RATE} Hz  ✓")
    print(f"  Bit depth   : 16-bit             ✓")
    print(f"  Channels    : Mono               ✓")
    print(f"  Peak ceiling: {ACX_PEAK_DB} dBFS          ✓")
    print(f"  RMS target  : {ACX_RMS_DB} dBFS         ✓")
    print("  Run audiobook_master.py for final mastering (noise floor, room tone).")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        description="Batch audiobook generator: Pocket TTS + voice cloning",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--text",        required=True,  help="Path to manuscript .txt file")
    p.add_argument("--voice",       required=True,  help="Path to reference voice .wav (5-20 sec, clean audio)")
    p.add_argument("--output_dir",  default="./audiobook_output", help="Directory for output files")
    p.add_argument("--title",       default="Audiobook",          help="Book title (used in filename)")
    p.add_argument("--pen_name",    default="Author",             help="Pen name (for logging)")
    p.add_argument("--chunk_size",  type=int, default=350,        help="Max chars per TTS call (default 350)")
    p.add_argument("--chapter_pause", type=float, default=2.0,   help="Silence gap between chapters in seconds")
    p.add_argument("--concat",      action="store_true",          help="Concatenate all chapters into one file")
    p.add_argument("--no_concat",   dest="concat", action="store_false")
    p.set_defaults(concat=True)
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.text):
        sys.exit(f"ERROR: Manuscript not found: {args.text}")
    if not os.path.exists(args.voice):
        sys.exit(f"ERROR: Voice reference not found: {args.voice}")
    if not args.voice.lower().endswith(".wav"):
        log.warning("Voice reference is not a .wav file — Pocket TTS works best with WAV.")

    run(args)
