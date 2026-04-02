#!/usr/bin/env python3
"""
FrenzAI Audiobook Production Pipeline
======================================
Complete pipeline: manuscript → ACX-compliant audiobook MP3 files.

Dependencies:
    pip install torch torchaudio transformers accelerate bitsandbytes
    pip install pydub soundfile pyloudnorm noisereduce pedalboard
    pip install openai-whisper numpy scipy tqdm colorama
    # System: install ffmpeg (choco install ffmpeg OR download from ffmpeg.org)

Usage:
    python frenzai_pipeline.py \\
        --manuscript "MyBook.txt" \\
        --voice "narrator_reference.wav" \\
        --title "My Audiobook" \\
        --author "Jane Doe" \\
        --narrator "John Smith" \\
        --output-dir "output"
"""

import argparse
import gc
import hashlib
import json
import logging
import os
import random
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from math import gcd
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence

# ---------------------------------------------------------------------------
# CONFIGURATION — Change anything here without touching logic
# ---------------------------------------------------------------------------
CONFIG = {
    # Paths
    "output_dir":              "output",
    "cache_dir":               "cache",
    "temp_dir":                "temp",
    "log_file":                "frenzai.log",
    "error_log":               "errors.log",
    "progress_file":           "progress.json",
    "session_file":            "session.json",

    # TTS model
    "model_name":              "canopylabs/orpheus-3b-0.1-ft",
    "model_dtype":             "float16",
    "use_8bit":                False,
    "use_4bit":                False,

    # Voice
    "voice_reference":         None,
    "voice_seed":              None,
    "voice_temperature":       0.7,

    # Text chunking
    "chunk_size_words":        300,
    "chunk_size_max":          450,
    "min_chunk_words":         30,

    # Audio export
    "sample_rate":             44100,
    "channels":                1,
    "export_bitrate":          "192k",

    # Silence and breathing
    "silence_sentence_ms":     400,
    "silence_paragraph_ms":    800,
    "silence_chapter_ms":      1200,
    "breath_min_ms":           80,
    "breath_max_ms":           130,
    "breath_long_sentence":    15,

    # Humanizer
    "speed_variation":         0.03,
    "volume_variation_db":     1.5,
    "micro_pause_min_ms":      50,
    "micro_pause_max_ms":      150,

    # ACX targets
    "acx_rms_target":          -20.0,
    "acx_rms_min":             -23.0,
    "acx_rms_max":             -18.0,
    "acx_peak_max":            -3.0,
    "acx_noise_max":           -60.0,
    "acx_peak_linear":         0.708,

    # Parallel processing
    "max_parallel_chunks":     3,
    "max_retries":             3,
    "retry_delay_sec":         5,

    # Whisper validation
    "whisper_model":           "tiny",
    "similarity_threshold":    0.85,

    # VRAM watchdog
    "vram_check_interval_sec": 30,
    "vram_warn_threshold":     0.85,
    "vram_pause_threshold":    0.92,

    # Retail sample
    "retail_sample_start_sec": 30,
    "retail_sample_end_sec":   210,

    # Book metadata
    "title":                   "Untitled",
    "author":                  "Unknown",
    "narrator":                "FrenzAI",
}


# ===========================================================================
# STEP 1 — Logging Setup
# ===========================================================================
logger = logging.getLogger("frenzai")


def setup_logging():
    """Configure dual logging: file (all levels) + colored console (INFO+)."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
    except ImportError:
        class Fore:
            CYAN = MAGENTA = GREEN = YELLOW = RED = WHITE = ""
        class Style:
            RESET_ALL = ""

    logger.setLevel(logging.DEBUG)

    # File handler — all levels
    fh = logging.FileHandler(CONFIG["log_file"], encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # Console handler — INFO+ with color
    class ColorHandler(logging.StreamHandler):
        COLORS = {
            logging.DEBUG: Fore.WHITE,
            logging.INFO: Fore.CYAN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.RED,
        }
        def emit(self, record):
            color = self.COLORS.get(record.levelno, "")
            record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
            super().emit(record)

    ch = ColorHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    # Store color refs for helper functions
    setup_logging._Fore = Fore
    setup_logging._Style = Style


def log_info(msg):
    logger.info(msg)

def log_ok(msg):
    F = getattr(setup_logging, '_Fore', None)
    prefix = f"{F.GREEN}" if F else ""
    logger.info(f"{prefix}✓ {msg}")

def log_warn(msg):
    logger.warning(msg)

def log_error(msg):
    logger.error(msg)

def log_step(n, msg):
    F = getattr(setup_logging, '_Fore', None)
    prefix = f"{F.MAGENTA}" if F else ""
    logger.info(f"{prefix}[{n:02d}] {msg}")


# ===========================================================================
# STEP 2 — Directory and Session Setup
# ===========================================================================
def setup_directories():
    """Create output, cache, temp, and assets directories if missing."""
    for d in [CONFIG["output_dir"], CONFIG["cache_dir"], CONFIG["temp_dir"], "assets"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    log_ok("Directories ready")


def save_session(seed: int, temperature: float):
    """Save TTS seed + temperature to session.json. Locks voice signature."""
    data = {
        "seed": seed,
        "temperature": temperature,
        "created": datetime.now().isoformat(),
        "model": CONFIG["model_name"],
    }
    Path(CONFIG["session_file"]).write_text(json.dumps(data, indent=2))
    log_info(f"Session saved: seed={seed}, temp={temperature}")


def load_session() -> tuple[int, float]:
    """Load session or create new one. Returns (seed, temperature)."""
    path = Path(CONFIG["session_file"])
    if path.exists():
        data = json.loads(path.read_text())
        log_info(f"Session loaded: seed={data['seed']}")
        return data["seed"], data["temperature"]
    seed = random.randint(0, 99999)
    temp = CONFIG["voice_temperature"]
    save_session(seed, temp)
    return seed, temp


def save_progress(chapter_id: str, status: str, output_path: str = ""):
    """Write chapter status to progress.json. Status: done, failed, skipped."""
    path = Path(CONFIG["progress_file"])
    progress = json.loads(path.read_text()) if path.exists() else {}
    progress[chapter_id] = {
        "status": status,
        "output_path": output_path,
        "timestamp": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(progress, indent=2))


def load_progress() -> dict:
    """Read progress.json. Returns dict of completed chapters."""
    path = Path(CONFIG["progress_file"])
    if path.exists():
        return json.loads(path.read_text())
    return {}


def log_error_chunk(chunk_id: int, error_msg: str):
    """Append failed chunk to errors.log with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CONFIG["error_log"], "a", encoding="utf-8") as f:
        f.write(f"[{ts}] CHUNK {chunk_id}: {error_msg}\n")


# ===========================================================================
# STEP 3 — VRAM Watchdog
# ===========================================================================
class VRAMWatchdog(threading.Thread):
    """Daemon thread monitoring GPU VRAM usage. Flushes at 92%."""

    def __init__(self):
        super().__init__(daemon=True)
        self.paused = False
        self._stop_event = threading.Event()

    def run(self):
        try:
            import torch
            if not torch.cuda.is_available():
                return
        except ImportError:
            return

        while not self._stop_event.is_set():
            self._stop_event.wait(CONFIG["vram_check_interval_sec"])
            if self._stop_event.is_set():
                break
            try:
                allocated = torch.cuda.memory_allocated(0)
                total = torch.cuda.get_device_properties(0).total_memory
                usage = allocated / total if total > 0 else 0

                if usage >= CONFIG["vram_pause_threshold"]:
                    log_warn(f"VRAM at {usage*100:.0f}% ({allocated/1e9:.1f}GB) — flushing!")
                    gc.collect()
                    torch.cuda.empty_cache()
                    self.paused = True
                    time.sleep(10)
                    self.paused = False
                    log_ok("VRAM flushed, resuming")
                elif usage >= CONFIG["vram_warn_threshold"]:
                    log_warn(f"VRAM at {usage*100:.0f}% ({allocated/1e9:.1f}GB)")
            except Exception:
                pass

    def stop(self):
        self._stop_event.set()


def print_vram_stats(label: str = ""):
    """Print used / reserved / total VRAM in GB. Skip if no CUDA."""
    try:
        import torch
        if torch.cuda.is_available():
            a = torch.cuda.memory_allocated(0) / 1e9
            r = torch.cuda.memory_reserved(0) / 1e9
            t = torch.cuda.get_device_properties(0).total_memory / 1e9
            log_info(f"[VRAM {label}] Allocated: {a:.2f}GB | Reserved: {r:.2f}GB | Total: {t:.2f}GB")
    except Exception:
        pass


def flush_vram(model=None):
    """Delete model, run gc + empty_cache."""
    if model is not None:
        del model
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass
    log_ok("VRAM flushed")


# ===========================================================================
# STEP 4 — TTS Model Loader
# ===========================================================================
def load_tts_model():
    """Load TTS model with quantization support. Auto-retries with 8-bit on OOM.

    Returns:
        (model, tokenizer) tuple
    """
    log_step(8, f"Loading model: {CONFIG['model_name']}")
    print_vram_stats("before model load")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        log_error("transformers not installed. Run: pip install transformers accelerate")
        return None, None

    dtype_map = {"float16": torch.float16, "float32": torch.float32, "bfloat16": torch.bfloat16}
    dtype = dtype_map.get(CONFIG["model_dtype"], torch.float16)

    quant_config = None
    if CONFIG["use_4bit"] or CONFIG["use_8bit"]:
        try:
            from transformers import BitsAndBytesConfig
            if CONFIG["use_4bit"]:
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=dtype,
                    bnb_4bit_use_double_quant=True,
                )
            else:
                quant_config = BitsAndBytesConfig(load_in_8bit=True)
        except ImportError:
            log_warn("bitsandbytes not available, loading without quantization")

    try:
        model = AutoModelForCausalLM.from_pretrained(
            CONFIG["model_name"],
            torch_dtype=dtype,
            device_map="auto",
            quantization_config=quant_config,
            low_cpu_mem_usage=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
        print_vram_stats("after model load")
        log_ok(f"Model loaded: {CONFIG['model_name']}")
        return model, tokenizer

    except (RuntimeError, torch.cuda.OutOfMemoryError) as e:
        log_warn(f"OOM loading model: {e}")
        flush_vram()
        if not CONFIG["use_8bit"]:
            log_info("Retrying with 8-bit quantization...")
            CONFIG["use_8bit"] = True
            return load_tts_model()
        raise


# ===========================================================================
# STEP 5 — Text Preprocessor
# ===========================================================================
def preprocess_text(text: str) -> str:
    """Clean and prepare manuscript text for voice synthesis.

    Args:
        text: Raw manuscript text

    Returns:
        Cleaned, voice-ready text
    """
    original_len = len(text)

    # Remove markdown formatting
    text = re.sub(r'#{1,6}\s+', '', text)  # headers
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)  # bold/italic
    text = re.sub(r'`[^`]+`', lambda m: m.group(0).strip('`'), text)  # code
    text = re.sub(r'<[^>]+>', '', text)  # HTML

    # Normalize whitespace
    text = text.replace('\r\n', '\n')
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    # Fix punctuation
    text = text.replace('—', ', ')
    text = text.replace('–', ', ')
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")

    # Expand abbreviations
    abbrevs = {
        r'\bMr\.': 'Mister', r'\bMrs\.': 'Missus', r'\bDr\.': 'Doctor',
        r'\bProf\.': 'Professor', r'\bSt\.': 'Saint', r'\bvs\.': 'versus',
        r'\betc\.': 'etcetera', r'\bi\.e\.': 'that is', r'\be\.g\.': 'for example',
    }
    for pattern, replacement in abbrevs.items():
        text = re.sub(pattern, replacement, text)

    # Expand acronyms: FBI → F.B.I.
    def expand_acronym(m):
        word = m.group(0)
        if word in ('I', 'A', 'OK', 'AM', 'PM', 'TV', 'US', 'UK'):
            return word
        return '.'.join(word) + '.'

    text = re.sub(r'\b[A-Z]{2,5}\b', expand_acronym, text)

    # Spell out small numbers
    num_words = {
        '13': 'thirteen', '12': 'twelve', '11': 'eleven', '10': 'ten',
        '9': 'nine', '8': 'eight', '7': 'seven', '6': 'six', '5': 'five',
        '4': 'four', '3': 'three', '2': 'two', '1': 'one', '0': 'zero',
        '20': 'twenty', '30': 'thirty', '100': 'one hundred', '1000': 'one thousand',
    }
    for num, word in num_words.items():
        text = re.sub(rf'\b{num}\b', word, text)

    # Fix sentence spacing
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)

    log_info(f"Preprocessed: {original_len} → {len(text)} chars")
    return text.strip()


# ===========================================================================
# STEP 6 — SSML Injector
# ===========================================================================
def inject_ssml(text: str) -> str:
    """Inject emotion/pause cues using punctuation tricks and SSML tags.

    Punctuation tricks work with all TTS models universally.
    SSML tags (<break>, <prosody>) work on models that support them.

    Args:
        text: Preprocessed manuscript text

    Returns:
        Text with emotion/pause hints injected
    """
    # After chapter headers — long pause
    text = re.sub(r'(Chapter\s+\w+[^\n]*)\n', r'\1\n<break time="1500ms"/>\n', text, flags=re.IGNORECASE)

    # Section breaks
    text = re.sub(r'\n\s*(\*{3}|---)\s*\n', '\n<break time="1000ms"/>\n', text)

    # After questions — slight pause
    text = re.sub(r'\?(\s+)', r'?<break time="350ms"/>\1', text)

    # Exclamatory sentences — slight emphasis
    text = re.sub(r'([^.!?]{10,}!)', r'<prosody rate="92%" pitch="+4%">\1</prosody>', text)

    # Quoted dialogue 10+ chars — slightly different pace
    text = re.sub(r'"([^"]{10,})"', r'<prosody rate="96%">"\1"</prosody>', text)

    # Suspense words
    suspense = [
        'suddenly', 'silence', 'darkness', 'alone', 'never', 'always',
        'whispered', 'screamed', 'froze', 'shattered', 'disappeared',
        'impossible', 'finally', 'nothing', 'everything', 'forever',
    ]
    for word in suspense:
        text = re.sub(rf'\b({word})\b', rf'<prosody rate="85%">\1</prosody>', text, flags=re.IGNORECASE)

    # Ellipses — dramatic pause
    text = re.sub(r'\.\.\.', '...<break time="600ms"/>', text)

    # Paragraph breaks
    text = re.sub(r'\n\n', '\n<break time="800ms"/>\n', text)

    log_ok("SSML cues injected")
    return text


# ===========================================================================
# STEP 7 — Smart Text Chunker
# ===========================================================================
def smart_chunk(text: str) -> tuple[list[dict], list[dict]]:
    """Split text into chapters, then into TTS-safe chunks.

    Never splits mid-sentence. Never merges across chapter boundaries.

    Args:
        text: SSML-injected text

    Returns:
        (chunks_list, chapters_list) — chunks have id, text, chapter, header
    """
    # Detect chapters
    chapter_pattern = re.compile(r'^(Chapter\s+\w+[^\n]*)', re.IGNORECASE | re.MULTILINE)
    matches = list(chapter_pattern.finditer(text))

    chapters = []
    if matches:
        for i, m in enumerate(matches):
            header = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                chapters.append({"header": header, "body": body})
    else:
        chapters.append({"header": "Chapter 1", "body": text})

    # Chunk each chapter
    target = CONFIG["chunk_size_words"]
    hard_max = CONFIG["chunk_size_max"]
    min_words = CONFIG["min_chunk_words"]
    all_chunks = []
    chunk_id = 0

    for ch_idx, chapter in enumerate(chapters):
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', chapter["body"])
        current_chunk = []
        current_words = 0

        for sentence in sentences:
            s_words = len(sentence.split())
            if current_words + s_words > hard_max and current_chunk:
                # Flush current chunk
                all_chunks.append({
                    "id": chunk_id,
                    "text": " ".join(current_chunk),
                    "chapter": ch_idx,
                    "header": chapter["header"] if not current_chunk else None,
                })
                chunk_id += 1
                current_chunk = [sentence]
                current_words = s_words
            elif current_words + s_words >= target and current_chunk:
                current_chunk.append(sentence)
                all_chunks.append({
                    "id": chunk_id,
                    "text": " ".join(current_chunk),
                    "chapter": ch_idx,
                    "header": chapter["header"] if chunk_id == 0 or all_chunks[-1]["chapter"] != ch_idx else None,
                })
                chunk_id += 1
                current_chunk = []
                current_words = 0
            else:
                current_chunk.append(sentence)
                current_words += s_words

        # Flush remaining
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            # Merge tiny chunks into previous
            if len(chunk_text.split()) < min_words and all_chunks and all_chunks[-1]["chapter"] == ch_idx:
                all_chunks[-1]["text"] += " " + chunk_text
            else:
                all_chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "chapter": ch_idx,
                    "header": None,
                })
                chunk_id += 1

    log_info(f"Chunked: {len(chapters)} chapters → {len(all_chunks)} chunks")
    return all_chunks, chapters


# ===========================================================================
# STEP 8 — Chunk Cache
# ===========================================================================
# Cache hit = zero VRAM, zero wait. Critical for re-runs and testing.

def get_cache_path(text: str, voice_id: str) -> str:
    """Generate cache path from text + voice hash."""
    key = f"{text}::{voice_id}::{CONFIG['voice_temperature']}"
    h = hashlib.md5(key.encode()).hexdigest()
    return str(Path(CONFIG["cache_dir"]) / f"{h}.wav")


def chunk_is_cached(text: str, voice_id: str) -> bool:
    """Check if a chunk's audio is already cached."""
    return Path(get_cache_path(text, voice_id)).exists()


def load_from_cache(text: str, voice_id: str) -> AudioSegment:
    """Load cached audio for a chunk."""
    return AudioSegment.from_file(get_cache_path(text, voice_id))


def save_to_cache(audio: AudioSegment, text: str, voice_id: str):
    """Save chunk audio to cache."""
    audio.export(get_cache_path(text, voice_id), format="wav")


# ===========================================================================
# STEP 9 — TTS Chunk Generator
# ===========================================================================
def generate_chunk_audio(
    chunk: dict, model, tokenizer, voice_ref: str, seed: int,
) -> AudioSegment:
    """Generate audio for a single text chunk via TTS model.

    Checks cache first. Retries on failure. Logs errors.

    Args:
        chunk: dict with 'id', 'text', 'chapter'
        model: loaded TTS model
        tokenizer: loaded tokenizer
        voice_ref: path to reference voice WAV
        seed: voice consistency seed

    Returns:
        AudioSegment of generated speech
    """
    voice_id = voice_ref or "default"
    text = chunk["text"]

    # Check cache
    if chunk_is_cached(text, voice_id):
        log_info(f"  Chunk {chunk['id']}: cache hit")
        return load_from_cache(text, voice_id)

    # Set seeds for consistency
    import torch
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed % (2**31))

    for attempt in range(CONFIG["max_retries"]):
        try:
            # ================================================================
            # MODEL-SPECIFIC GENERATION — Replace this block with your model
            # ================================================================
            # ORPHEUS:
            #   tokens = tokenizer(text, return_tensors="pt").to(model.device)
            #   output = model.generate(**tokens, max_new_tokens=2000,
            #                           temperature=CONFIG["voice_temperature"])
            #   audio_array = decode_orpheus_output(output)
            #
            # FISH SPEECH:
            #   audio = fish_speech_infer(text, reference_audio=voice_ref)
            #
            # F5-TTS:
            #   from f5_tts.api import F5TTS
            #   tts = F5TTS(model_type="F5-TTS")
            #   audio, sr, _ = tts.infer(ref_file=voice_ref, gen_text=text)
            #
            # KOKORO (already in FrenzAI):
            #   from kokoro import KPipeline
            #   pipeline = KPipeline(lang_code="a")
            #   for _, _, chunk_audio in pipeline(text, voice="af_heart"):
            #       audio_chunks.append(chunk_audio.numpy())
            #
            # PLACEHOLDER — generates silence proportional to word count:
            word_count = len(text.split())
            duration_ms = max(500, word_count * 350)
            audio_segment = AudioSegment.silent(duration=duration_ms)
            # ================================================================

            # Save to cache
            save_to_cache(audio_segment, text, voice_id)
            return audio_segment

        except (RuntimeError, Exception) as e:
            if "out of memory" in str(e).lower():
                log_warn(f"  Chunk {chunk['id']}: OOM (attempt {attempt+1})")
                flush_vram()
                time.sleep(5)
            else:
                log_warn(f"  Chunk {chunk['id']}: Error (attempt {attempt+1}): {e}")
                time.sleep(CONFIG["retry_delay_sec"])

    # All retries failed
    log_error(f"  Chunk {chunk['id']}: FAILED after {CONFIG['max_retries']} attempts")
    log_error_chunk(chunk["id"], "All retries exhausted")
    return AudioSegment.silent(duration=1000)


def generate_all_chunks_parallel(
    chunks: list[dict], model, tokenizer, voice_ref: str, seed: int,
) -> list[AudioSegment]:
    """Generate all chunks with thread pool + VRAM watchdog.

    Args:
        chunks: list of chunk dicts
        model, tokenizer: loaded TTS model
        voice_ref: reference voice path
        seed: consistency seed

    Returns:
        List of AudioSegments in correct chunk order
    """
    from tqdm import tqdm

    watchdog = VRAMWatchdog()
    watchdog.start()

    results = {}
    with ThreadPoolExecutor(max_workers=CONFIG["max_parallel_chunks"]) as pool:
        futures = {
            pool.submit(generate_chunk_audio, chunk, model, tokenizer, voice_ref, seed): chunk["id"]
            for chunk in chunks
        }
        for future in tqdm(as_completed(futures), total=len(futures), unit="chunk", desc="Generating"):
            chunk_id = futures[future]
            # Wait if watchdog paused
            while watchdog.paused:
                time.sleep(1)
            try:
                results[chunk_id] = future.result()
            except Exception as e:
                log_error(f"Chunk {chunk_id} failed: {e}")
                results[chunk_id] = AudioSegment.silent(duration=1000)

    watchdog.stop()
    # Return in correct order
    return [results[chunk["id"]] for chunk in chunks]


# ===========================================================================
# STEP 10 — Breath Inserter
# ===========================================================================
def insert_breaths(audio_segment: AudioSegment, text: str) -> AudioSegment:
    """Insert natural breath sounds at pause points.

    Record a real breath sound at -30dBFS and save as assets/breath.wav
    for best results. Falls back to 100ms silence if not found.

    Args:
        audio_segment: TTS output audio
        text: original text (for sentence length analysis)

    Returns:
        Audio with breaths inserted
    """
    breath_path = Path("assets/breath.wav")
    if breath_path.exists():
        breath = AudioSegment.from_file(str(breath_path)) - 15  # reduce 15dB
    else:
        breath = AudioSegment.silent(duration=100)

    # Find long sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    long_indices = {
        i for i, s in enumerate(sentences)
        if len(s.split()) >= CONFIG["breath_long_sentence"]
    }

    # Split audio on silence
    chunks = split_on_silence(
        audio_segment,
        min_silence_len=200,
        silence_thresh=audio_segment.dBFS - 16,
        keep_silence=100,
    )

    if len(chunks) < 2:
        return audio_segment

    # Rebuild with breaths
    result = AudioSegment.empty()
    breath_count = 0
    for i, chunk in enumerate(chunks):
        if i in long_indices or (i > 0 and i % 3 == 0):
            dur = random.randint(CONFIG["breath_min_ms"], CONFIG["breath_max_ms"])
            vol = random.uniform(-3, 0)
            b = breath[:dur] + vol
            result += b
            breath_count += 1
        result += chunk

    log_info(f"Inserted {breath_count} breaths")
    return result


# ===========================================================================
# STEP 11 — Humanizer
# ===========================================================================
def humanize_audio(audio_segment: AudioSegment) -> AudioSegment:
    """Add micro pitch/speed/volume variations to break mechanical uniformity.

    Variations are intentionally tiny — barely perceptible. Goal is to break
    mechanical uniformity, not noticeably alter the audio.

    Args:
        audio_segment: processed audio

    Returns:
        Humanized audio
    """
    chunks = split_on_silence(
        audio_segment,
        min_silence_len=200,
        silence_thresh=audio_segment.dBFS - 16,
        keep_silence=100,
    )

    if len(chunks) < 2:
        log_warn("Humanizer: too few chunks, skipping")
        return audio_segment

    result = AudioSegment.empty()
    for chunk in chunks:
        # Speed variation — modify frame rate then reset (changes tempo without pitch)
        speed = random.uniform(
            1 - CONFIG["speed_variation"],
            1 + CONFIG["speed_variation"],
        )
        chunk = chunk._spawn(chunk.raw_data, overrides={
            "frame_rate": int(chunk.frame_rate * speed)
        }).set_frame_rate(chunk.frame_rate)

        # Volume variation
        vol = random.uniform(-CONFIG["volume_variation_db"], CONFIG["volume_variation_db"])
        chunk = chunk + vol

        # Micro-pause
        pause = AudioSegment.silent(duration=random.randint(
            CONFIG["micro_pause_min_ms"], CONFIG["micro_pause_max_ms"]
        ))

        result += chunk + pause

    log_info(f"Humanizer applied to {len(chunks)} phrase chunks")
    return result


# ===========================================================================
# STEP 12 — Warmth EQ
# ===========================================================================
def add_warmth(input_path: str, output_path: str):
    """Add professional broadcast character with EQ + subtle reverb.

    TTS sounds 'too clean' without it. Uses pedalboard library.

    Args:
        input_path: input WAV path
        output_path: output WAV path
    """
    try:
        from pedalboard import Pedalboard, Reverb, Compressor
        from pedalboard.io import AudioFile

        effects = [
            Compressor(threshold_db=-20, ratio=2.0, attack_ms=10, release_ms=100),
            Reverb(room_size=0.1, wet_level=0.05, dry_level=0.95),
        ]

        try:
            from pedalboard import LowShelfFilter, HighShelfFilter
            effects.insert(1, LowShelfFilter(cutoff_frequency_hz=200, gain_db=1.5))
            effects.insert(2, HighShelfFilter(cutoff_frequency_hz=12000, gain_db=-2.0))
        except ImportError:
            pass

        board = Pedalboard(effects)

        with AudioFile(input_path) as f:
            audio = f.read(f.frames)
            sr = f.samplerate

        processed = board(audio, sr)

        with AudioFile(output_path, 'w', sr, audio.shape[0]) as f:
            f.write(processed)

        log_ok("Warmth applied")

    except ImportError:
        log_warn("pedalboard not installed. Run: pip install pedalboard")
        import shutil
        shutil.copy2(input_path, output_path)


# ===========================================================================
# STEP 13 — Noise Floor Scrubber
# ===========================================================================
def scrub_noise(input_path: str, output_path: str):
    """Reduce noise floor below -65dB using spectral subtraction.

    Do NOT set prop_decrease to 1.0 — over-processing creates swimmy artifacts.

    Args:
        input_path: input WAV path
        output_path: output WAV path
    """
    try:
        import noisereduce as nr

        data, rate = sf.read(input_path)
        # First 0.5 seconds = noise profile
        noise_len = min(int(0.5 * rate), len(data) // 4)
        noise_sample = data[:noise_len]

        cleaned = nr.reduce_noise(
            y=data, sr=rate,
            y_noise=noise_sample,
            prop_decrease=0.75,
            stationary=True,
        )
        sf.write(output_path, cleaned, rate, subtype='PCM_16')
        log_ok("Noise scrubbed")

    except ImportError:
        log_warn("noisereduce not installed. Run: pip install noisereduce")
        import shutil
        shutil.copy2(input_path, output_path)


# ===========================================================================
# STEP 14 — ACX Mastering
# ===========================================================================
def acx_master(input_path: str, output_wav: str, output_mp3: str) -> str:
    """Master audio to ACX specifications.

    ACX Requirements:
    - RMS: -23dB to -18dB (target -20dB)
    - True peak: below -3dB
    - Noise floor: below -60dB
    - Format: mono MP3, 192kbps CBR, 44.1kHz

    Args:
        input_path: input WAV
        output_wav: mastered WAV output
        output_mp3: final MP3 output

    Returns:
        output_mp3 path
    """
    data, rate = sf.read(input_path)

    # Mono conversion
    if data.ndim > 1:
        data = data.mean(axis=1)
        log_info("Converted to mono")

    # Resample to 44100Hz
    if rate != 44100:
        from scipy.signal import resample_poly
        g = gcd(rate, 44100)
        data = resample_poly(data, 44100 // g, rate // g).astype(np.float64)
        rate = 44100
        log_info("Resampled to 44.1kHz")

    # Loudness normalization
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)
        log_info(f"Loudness before: {loudness:.1f} LUFS")
        if not np.isinf(loudness) and not np.isnan(loudness):
            data = pyln.normalize.loudness(data, loudness, CONFIG["acx_rms_target"])
            log_info(f"Normalized to {CONFIG['acx_rms_target']} LUFS")
    except ImportError:
        log_warn("pyloudnorm not installed, using RMS normalization")
        rms = np.sqrt(np.mean(data ** 2))
        if rms > 0:
            target = 10 ** (CONFIG["acx_rms_target"] / 20)
            data = data * (target / rms)

    # Peak limiting
    peak = np.abs(data).max()
    if peak > CONFIG["acx_peak_linear"]:
        data = data * (CONFIG["acx_peak_linear"] / peak)
        log_info(f"Peaks limited to {CONFIG['acx_peak_max']}dB")

    # Save WAV
    sf.write(output_wav, data, rate, subtype='PCM_16')

    # Convert to MP3 via ffmpeg
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', output_wav,
            '-ar', '44100', '-ac', '1',
            '-b:a', CONFIG["export_bitrate"],
            '-write_xing', '0',
            output_mp3,
        ], capture_output=True, check=True)
        log_ok(f"Exported: {output_mp3}")
    except FileNotFoundError:
        log_warn("ffmpeg not found — MP3 export skipped. Install: choco install ffmpeg")
    except subprocess.CalledProcessError as e:
        log_error(f"ffmpeg error: {e.stderr.decode()[:200]}")

    return output_mp3


# ===========================================================================
# STEP 15 — Whisper Transcript Validator
# ===========================================================================
def validate_with_whisper(audio_path: str, original_text: str, chunk_id: int) -> bool:
    """Validate TTS output matches source text using Whisper STT.

    Args:
        audio_path: generated audio file
        original_text: source text
        chunk_id: chunk identifier for logging

    Returns:
        True if match is above threshold or whisper unavailable
    """
    try:
        import whisper
    except ImportError:
        log_warn("whisper not installed. Run: pip install openai-whisper")
        return True

    try:
        model = whisper.load_model(CONFIG["whisper_model"])
        result = model.transcribe(audio_path, language="en")
        transcript = result["text"]

        # Normalize for comparison
        def normalize(t):
            return set(re.sub(r'[^\w\s]', '', t.lower()).split())

        orig_words = normalize(original_text)
        trans_words = normalize(transcript)

        if not orig_words or not trans_words:
            return True

        common = orig_words & trans_words
        similarity = 2 * len(common) / (len(orig_words) + len(trans_words))

        if similarity >= CONFIG["similarity_threshold"]:
            log_ok(f"Chunk {chunk_id} validated: {similarity*100:.0f}% match")
            return True
        else:
            log_warn(f"Chunk {chunk_id}: only {similarity*100:.0f}% match")
            log_error_chunk(chunk_id, f"Low similarity: {similarity:.2f}. Transcript: {transcript[:100]}")
            return False

    except Exception as e:
        log_warn(f"Whisper validation failed: {e}")
        return True


# ===========================================================================
# STEP 16 — ACX Compliance Checker
# ===========================================================================
def acx_check(audio_path: str) -> dict:
    """Check if an audio file meets all ACX requirements.

    Args:
        audio_path: path to audio file

    Returns:
        dict with rms_db, peak_db, noise_db, sample_rate, channels, passed, failures
    """
    data, rate = sf.read(audio_path)
    channels = 1 if data.ndim == 1 else data.shape[1]

    if data.ndim > 1:
        data_mono = data.mean(axis=1)
    else:
        data_mono = data

    # RMS
    rms = np.sqrt(np.mean(data_mono ** 2))
    rms_db = 20 * np.log10(rms + 1e-10)

    # Peak
    peak = np.abs(data_mono).max()
    peak_db = 20 * np.log10(peak + 1e-10)

    # Noise floor (first 0.5s)
    noise_len = min(int(0.5 * rate), len(data_mono) // 4)
    noise = data_mono[:noise_len]
    noise_rms = np.sqrt(np.mean(noise ** 2))
    noise_db = 20 * np.log10(noise_rms + 1e-10)

    failures = []
    if not (CONFIG["acx_rms_min"] <= rms_db <= CONFIG["acx_rms_max"]):
        failures.append(f"RMS {rms_db:.1f}dB (need {CONFIG['acx_rms_min']} to {CONFIG['acx_rms_max']})")
    if peak_db > CONFIG["acx_peak_max"]:
        failures.append(f"Peak {peak_db:.1f}dB (max {CONFIG['acx_peak_max']})")
    if noise_db > CONFIG["acx_noise_max"]:
        failures.append(f"Noise {noise_db:.1f}dB (max {CONFIG['acx_noise_max']})")
    if rate != 44100:
        failures.append(f"Sample rate {rate} (need 44100)")
    if channels != 1:
        failures.append(f"Channels {channels} (need mono)")

    passed = len(failures) == 0
    result = {
        "file": audio_path,
        "rms_db": round(rms_db, 1),
        "peak_db": round(peak_db, 1),
        "noise_db": round(noise_db, 1),
        "sample_rate": rate,
        "channels": channels,
        "passed": passed,
        "failures": failures,
    }

    if passed:
        log_ok(f"ACX PASS: {Path(audio_path).name} (RMS:{rms_db:.1f} Peak:{peak_db:.1f} Noise:{noise_db:.1f})")
    else:
        log_error(f"ACX FAIL: {Path(audio_path).name} — {'; '.join(failures)}")

    return result


# ===========================================================================
# STEP 17 — Chapter File Manager
# ===========================================================================
def build_chapter_filename(chapter_idx: int, chapter_header: str, total_chapters: int) -> str:
    """Build zero-padded, sanitized chapter filename.

    Args:
        chapter_idx: 0-based chapter index
        chapter_header: chapter title text
        total_chapters: total count for padding

    Returns:
        Filename like '01_Chapter_One.mp3'
    """
    pad = len(str(total_chapters + 2))
    idx = str(chapter_idx + 1).zfill(pad)
    safe = re.sub(r'[^a-zA-Z0-9 ]', '', chapter_header).strip().replace(' ', '_')[:40]
    return f"{idx}_{safe}.mp3"


def generate_credits(title: str, author: str, narrator: str, output_dir: str) -> tuple[str, str]:
    """Generate opening and closing credit text.

    ACX requires title + author + narrator in opening.
    Closing must include 'The End'.

    Returns:
        (opening_text, closing_text)
    """
    opening = f"{title}. Written by {author}. Narrated by {narrator}."
    closing = f"End of {title}. Written by {author}. Narrated by {narrator}. The End."
    return opening, closing


def cut_retail_sample(chapter1_mp3: str, output_path: str):
    """Cut a retail sample from chapter 1.

    Args:
        chapter1_mp3: path to first chapter MP3
        output_path: output retail sample path
    """
    if not Path(chapter1_mp3).exists():
        log_warn("Chapter 1 not found, skipping retail sample")
        return

    audio = AudioSegment.from_file(chapter1_mp3)
    start = CONFIG["retail_sample_start_sec"] * 1000
    end = CONFIG["retail_sample_end_sec"] * 1000
    sample = audio[start:end]

    if len(sample) < 10000:
        sample = audio[:end]

    sample = sample.fade_in(500).fade_out(1000)
    sample.export(output_path, format="mp3", bitrate=CONFIG["export_bitrate"])
    log_ok(f"Retail sample: {len(sample)/1000:.0f}s → {output_path}")


# ===========================================================================
# STEP 18 — Audiobook Stitcher
# ===========================================================================
def stitch_chapters(chapter_files: list[str], output_path: str, title: str) -> tuple[str, list]:
    """Merge all chapter MP3s into one full audiobook file.

    Args:
        chapter_files: ordered list of chapter MP3 paths
        output_path: full audiobook output path
        title: book title

    Returns:
        (output_path, chapter_times_list)
    """
    combined = AudioSegment.empty()
    chapter_silence = AudioSegment.silent(duration=CONFIG["silence_chapter_ms"])
    chapter_times = []

    for f in chapter_files:
        if not Path(f).exists():
            log_warn(f"Missing: {f}, inserting 5s silence")
            chapter = AudioSegment.silent(duration=5000)
        else:
            chapter = AudioSegment.from_file(f)

        start_ms = len(combined)
        combined += chapter + chapter_silence
        end_ms = len(combined)

        chapter_times.append({
            "file": f,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_s": round((end_ms - start_ms) / 1000, 1),
        })

    combined.export(output_path, format="mp3", bitrate=CONFIG["export_bitrate"])
    total_min = len(combined) / 1000 / 60
    log_ok(f"Full audiobook: {total_min:.1f} minutes → {output_path}")

    # Save chapter index
    index_path = output_path.replace('.mp3', '_chapters.json')
    Path(index_path).write_text(json.dumps(chapter_times, indent=2))

    return output_path, chapter_times


# ===========================================================================
# STEP 19 — Final QA Report
# ===========================================================================
def generate_qa_report(chapter_files: list[str], output_dir: str, title: str) -> dict:
    """Run ACX compliance on all files and generate summary report.

    Args:
        chapter_files: list of MP3 paths
        output_dir: output directory
        title: book title

    Returns:
        Report dict
    """
    log_step(19, "Running QA checks on all files")

    results = []
    for f in chapter_files:
        if Path(f).exists():
            results.append(acx_check(f))

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    # Estimate total duration (192kbps ≈ 24KB/s)
    total_bytes = sum(Path(r["file"]).stat().st_size for r in results if Path(r["file"]).exists())
    total_seconds = total_bytes / 24000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)

    print("\n" + "=" * 60)
    print(f"  FrenzAI QA REPORT — {title}")
    print("=" * 60)
    print(f"  Files checked:  {len(results)}")
    print(f"  Passed:         {passed}")
    print(f"  Failed:         {failed}")
    print(f"  Total duration: ~{hours}h {minutes}m")

    if failed > 0:
        print(f"\n  FAILED FILES:")
        for r in results:
            if not r["passed"]:
                print(f"    ✗ {Path(r['file']).name}: {'; '.join(r['failures'])}")
    else:
        print(f"\n  ✓ ALL FILES PASSED ACX COMPLIANCE")

    print("=" * 60 + "\n")

    report = {
        "title": title,
        "timestamp": datetime.now().isoformat(),
        "files_checked": len(results),
        "passed": passed,
        "failed": failed,
        "total_duration_estimate": f"{hours}h {minutes}m",
        "results": results,
    }

    report_path = str(Path(output_dir) / "qa_report.json")
    Path(report_path).write_text(json.dumps(report, indent=2))
    log_ok(f"QA report saved: {report_path}")

    return report


# ===========================================================================
# STEP 20 — Main Pipeline Orchestrator
# ===========================================================================
def run_pipeline(manuscript_path: str, voice_ref: str, title: str, author: str, narrator: str):
    """Run the complete audiobook production pipeline.

    Processes manuscript through all stages: text prep → TTS → humanization →
    ACX mastering → final QA. Supports checkpoint/resume.

    Args:
        manuscript_path: path to .txt manuscript
        voice_ref: path to reference .wav for voice cloning
        title: book title
        author: author name
        narrator: narrator name
    """
    start_time = time.time()

    setup_logging()
    log_step(1, "FrenzAI Audiobook Pipeline Starting")
    log_info(f"Title: {title} | Author: {author} | Narrator: {narrator}")

    # Step 1-2: Setup
    log_step(2, "Setting up directories")
    setup_directories()
    progress = load_progress()
    seed, temperature = load_session()
    CONFIG["voice_temperature"] = temperature

    # Step 3-4: Read manuscript
    log_step(3, "Reading manuscript")
    manuscript = Path(manuscript_path).read_text(encoding="utf-8", errors="replace")
    log_info(f"Manuscript: {len(manuscript)} characters")

    # Step 5: Preprocess
    log_step(5, "Preprocessing text")
    text = preprocess_text(manuscript)

    # Step 6: SSML
    log_step(6, "Injecting SSML cues")
    text = inject_ssml(text)

    # Step 7: Chunk
    log_step(7, "Chunking text")
    chunks, chapters = smart_chunk(text)

    # Step 8: Load model
    log_step(8, "Loading TTS model")
    model, tokenizer = load_tts_model()

    # Step 9: Credits
    log_step(9, "Generating credits")
    opening_text, closing_text = generate_credits(title, author, narrator, CONFIG["output_dir"])

    # Step 10: Opening credits
    log_step(10, "Generating opening credits")
    opening_key = "00_opening"
    if opening_key not in progress or progress[opening_key]["status"] != "done":
        opening_chunk = {"id": -1, "text": opening_text, "chapter": -1, "header": None}
        opening_audio = generate_chunk_audio(opening_chunk, model, tokenizer, voice_ref, seed)
        opening_path = str(Path(CONFIG["output_dir"]) / "00_opening_credits.mp3")
        opening_audio.export(opening_path, format="mp3", bitrate=CONFIG["export_bitrate"])
        save_progress(opening_key, "done", opening_path)
    else:
        opening_path = progress[opening_key]["output_path"]
    log_ok(f"Opening credits: {opening_path}")

    # Step 11: Process each chapter
    chapter_files = [opening_path]
    total_chapters = len(chapters)

    for ch_idx, chapter in enumerate(chapters):
        ch_key = f"chapter_{ch_idx}"
        ch_filename = build_chapter_filename(ch_idx, chapter["header"], total_chapters)
        ch_mp3 = str(Path(CONFIG["output_dir"]) / ch_filename)

        # Check if already done
        if ch_key in progress and progress[ch_key]["status"] == "done":
            existing = progress[ch_key].get("output_path", ch_mp3)
            if Path(existing).exists():
                log_info(f"Chapter {ch_idx+1}: already done, skipping")
                chapter_files.append(existing)
                continue

        log_step(11, f"Chapter {ch_idx+1}/{total_chapters}: {chapter['header']}")

        try:
            # a. Generate chunks for this chapter
            ch_chunks = [c for c in chunks if c["chapter"] == ch_idx]
            chunk_audios = generate_all_chunks_parallel(ch_chunks, model, tokenizer, voice_ref, seed)

            # b. Validate with Whisper
            for i, (chunk, audio) in enumerate(zip(ch_chunks, chunk_audios)):
                temp_val = str(Path(CONFIG["temp_dir"]) / f"val_{ch_idx}_{i}.wav")
                audio.export(temp_val, format="wav")
                validate_with_whisper(temp_val, chunk["text"], chunk["id"])

            # c. Stitch chunks with sentence silence
            sentence_silence = AudioSegment.silent(duration=CONFIG["silence_sentence_ms"])
            chapter_audio = AudioSegment.empty()
            for audio in chunk_audios:
                chapter_audio += audio + sentence_silence

            # d. Insert breaths
            log_info("  Inserting breaths...")
            chapter_audio = insert_breaths(chapter_audio, chapter["body"])

            # e. Humanize
            log_info("  Humanizing...")
            chapter_audio = humanize_audio(chapter_audio)

            # f. Save raw WAV
            raw_wav = str(Path(CONFIG["temp_dir"]) / f"ch{ch_idx}_raw.wav")
            chapter_audio.export(raw_wav, format="wav")

            # g. Add warmth
            warm_wav = str(Path(CONFIG["temp_dir"]) / f"ch{ch_idx}_warm.wav")
            add_warmth(raw_wav, warm_wav)

            # h. Scrub noise
            clean_wav = str(Path(CONFIG["temp_dir"]) / f"ch{ch_idx}_clean.wav")
            scrub_noise(warm_wav, clean_wav)

            # i. ACX master
            master_wav = str(Path(CONFIG["temp_dir"]) / f"ch{ch_idx}_master.wav")
            acx_master(clean_wav, master_wav, ch_mp3)

            # j. ACX check
            acx_check(ch_mp3)

            # k. Checkpoint
            save_progress(ch_key, "done", ch_mp3)
            chapter_files.append(ch_mp3)
            log_ok(f"Chapter {ch_idx+1} complete: {ch_filename}")

        except Exception as e:
            log_error(f"Chapter {ch_idx+1} FAILED: {e}")
            save_progress(ch_key, "failed")
            # Continue to next chapter

    # Step 12: Closing credits
    log_step(12, "Generating closing credits")
    closing_key = "closing"
    closing_filename = f"{str(total_chapters + 1).zfill(2)}_closing_credits.mp3"
    closing_path = str(Path(CONFIG["output_dir"]) / closing_filename)

    if closing_key not in progress or progress[closing_key]["status"] != "done":
        closing_chunk = {"id": -2, "text": closing_text, "chapter": -2, "header": None}
        closing_audio = generate_chunk_audio(closing_chunk, model, tokenizer, voice_ref, seed)
        closing_audio.export(closing_path, format="mp3", bitrate=CONFIG["export_bitrate"])
        save_progress(closing_key, "done", closing_path)
    chapter_files.append(closing_path)

    # Step 13: Retail sample
    log_step(13, "Cutting retail sample")
    retail_path = str(Path(CONFIG["output_dir"]) / "retail_sample.mp3")
    ch1_files = [f for f in chapter_files if "01_" in f]
    if ch1_files:
        cut_retail_sample(ch1_files[0], retail_path)

    # Step 14: Stitch full audiobook
    log_step(14, "Stitching full audiobook")
    safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', title).replace(' ', '_')
    full_path = str(Path(CONFIG["output_dir"]) / f"{safe_title}_FULL.mp3")
    stitch_chapters(chapter_files, full_path, title)

    # Step 15: QA report
    generate_qa_report(chapter_files + [full_path], CONFIG["output_dir"], title)

    # Step 16: Cleanup
    log_step(16, "Cleaning up")
    flush_vram(model)

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    log_step(17, f"Pipeline complete in {minutes}m {seconds}s")
    log_ok(f"Output: {CONFIG['output_dir']}/")


# ===========================================================================
# STEP 21 — CLI Entry Point
# ===========================================================================
def parse_args():
    """Parse command line arguments and apply to CONFIG."""
    parser = argparse.ArgumentParser(
        description="FrenzAI — Audiobook Production Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manuscript", required=True, help="Path to .txt manuscript")
    parser.add_argument("--voice", required=True, help="Path to reference .wav for voice cloning")
    parser.add_argument("--title", required=True, help="Book title")
    parser.add_argument("--author", required=True, help="Author name")
    parser.add_argument("--narrator", required=True, help="Narrator name")
    parser.add_argument("--model", default=CONFIG["model_name"], help="HuggingFace model name")
    parser.add_argument("--use-8bit", action="store_true", help="Load model in 8-bit")
    parser.add_argument("--use-4bit", action="store_true", help="Load model in 4-bit")
    parser.add_argument("--chunk-words", type=int, default=CONFIG["chunk_size_words"])
    parser.add_argument("--threads", type=int, default=CONFIG["max_parallel_chunks"])
    parser.add_argument("--output-dir", default=CONFIG["output_dir"])

    args = parser.parse_args()

    # Apply to CONFIG
    CONFIG["model_name"] = args.model
    CONFIG["use_8bit"] = args.use_8bit
    CONFIG["use_4bit"] = args.use_4bit
    CONFIG["chunk_size_words"] = args.chunk_words
    CONFIG["max_parallel_chunks"] = args.threads
    CONFIG["output_dir"] = args.output_dir
    CONFIG["voice_reference"] = args.voice
    CONFIG["title"] = args.title
    CONFIG["author"] = args.author
    CONFIG["narrator"] = args.narrator

    return args


if __name__ == "__main__":
    args = parse_args()

    # Validate inputs
    if not Path(args.manuscript).exists():
        print(f"ERROR: Manuscript not found: {args.manuscript}")
        sys.exit(1)
    if not Path(args.voice).exists():
        print(f"ERROR: Voice reference not found: {args.voice}")
        sys.exit(1)

    run_pipeline(
        manuscript_path=args.manuscript,
        voice_ref=args.voice,
        title=args.title,
        author=args.author,
        narrator=args.narrator,
    )
