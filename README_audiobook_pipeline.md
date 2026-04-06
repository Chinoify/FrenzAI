# Audiobook Pipeline — Pocket TTS + Voice Cloning
## Setup & Usage Guide

---

## 1. Install dependencies (one-time)

```bash
# Python 3.10–3.14 required
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install pocket-tts scipy soundfile numpy tqdm
```

No GPU needed. No CUDA. The CPU-only PyTorch wheel works perfectly.

---

## 2. Prepare your voice reference

Record or export a clean 10–20 second WAV clip of your narrator voice.

**Requirements for best cloning:**
- Single speaker, no background noise
- Natural speaking pace (audiobook narration style)
- 24kHz or higher sample rate
- WAV format (.wav)

Then run the prep utility:
```bash
python voice_prep.py --input my_recording.wav
# Outputs: my_recording_prepped.wav (cleaned, normalized, trimmed)
```

---

## 3. Generate a single audiobook

```bash
python audiobook_pocket_tts.py \
    --text manuscript.txt \
    --voice my_recording_prepped.wav \
    --output_dir ./audiobooks/my_book \
    --title "My Book Title" \
    --pen_name "Grace Ifeoma Ezedinma" \
    --concat
```

**What it does:**
- Detects chapter breaks automatically (Chapter 1, CHAPTER ONE, Part 1, ---, ***, etc.)
- Splits each chapter into ~350-character chunks for optimal TTS quality
- Synthesizes each chunk using the cloned voice
- Normalizes each chapter to ACX standards (-20 dBFS RMS, -3 dBFS peak)
- Resamples to 44.1kHz 16-bit mono (ACX/Audible requirement)
- Saves per-chapter WAV files + one full audiobook WAV
- Saves progress — safe to Ctrl+C and resume anytime

---

## 4. Batch process your full catalog

Edit the `CATALOG` list inside `audiobook_batch_catalog.py` with your:
- Pen names
- Voice WAV paths (one per pen name)
- Book titles + manuscript paths

Then run:
```bash
# Full catalog
python audiobook_batch_catalog.py

# One pen name only
python audiobook_batch_catalog.py --pen_name "Grace Ifeoma Ezedinma"

# One book only
python audiobook_batch_catalog.py --title "Leave and Cleave"

# Skip already-completed books
python audiobook_batch_catalog.py --skip_done

# Dry run (print commands without executing)
python audiobook_batch_catalog.py --dry_run
```

---

## 5. Output structure

```
audiobooks/
  grace_ifeoma/
    leave_and_cleave/
      chapters/
        ch001_Chapter_1.wav
        ch002_Chapter_2.wav
        ...
      Leave_and_Cleave_FULL_AUDIOBOOK.wav   ← upload this to ACX
      progress.json                          ← resume state
```

---

## 6. Final mastering

After generation, run your existing `audiobook_master.py` on the FULL_AUDIOBOOK.wav
for final noise floor treatment, room tone, and ACX compliance verification.

The scripts already output:
- ✅ 44.1kHz sample rate
- ✅ 16-bit depth
- ✅ Mono
- ✅ -20 dBFS RMS (±2 dB)
- ✅ -3 dBFS peak ceiling

---

## 7. Speed expectations (CPU, no GPU)

| Hardware          | Speed                    | 1 hr audiobook |
|-------------------|--------------------------|----------------|
| MacBook Air M4    | 6× real-time             | ~10 min        |
| Modern i7/Ryzen 7 | ~3–5× real-time          | ~15–20 min     |
| Older i5 (2018)   | ~1–2× real-time          | ~30–60 min     |

Pocket TTS only uses 2 CPU cores, so you can run other tasks simultaneously.

---

## 8. Tips for voice quality

- **Record in a quiet room** — Pocket TTS clones room acoustics too.
- **Match narration style** — if your audiobook is calm/storytelling, record calmly.
- **One voice WAV per pen name** — store them in a `./voices/` folder.
- **Don't re-load the model** — the batch scripts keep the model in memory across chapters.
- **Chunk size** — default 350 chars works well. If you get cut-off sentences, lower to 250.

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: pocket_tts` | Run `pip install pocket-tts` |
| `torch not found` | Run `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| Voice sounds wrong | Re-prep reference WAV with `voice_prep.py` |
| Chapters not detected | Add `Chapter X` headers to manuscript manually |
| Progress file corrupted | Delete `progress.json` and re-run (safe to restart) |
| Output too quiet/loud | Run `audiobook_master.py` post-processing |
