# FrenzAI — Project Instructions

## GPU / VRAM Rules
- GPU: NVIDIA GeForce GTX 970 — 4GB dedicated VRAM, 12GB shared
- Always load models with `torch_dtype=torch.float16` and `device_map="auto"`
- Always add `BitsAndBytesConfig(load_in_8bit=True)` if model exceeds 4GB
- Always clean up VRAM with `del model` + `gc.collect()` + `torch.cuda.empty_cache()` between model loads
- Print VRAM stats before and after every model load
- Only one TTS model loaded in GPU at a time (engine_registry enforces this)

## App Name
- App name is **FrenzAI** (not VoiceForge Studio)
- Bat file is `Start FrenzAI.bat`

## Tech Stack
- Backend: Python 3.12 + FastAPI + SQLAlchemy + SQLite
- Frontend: React + TypeScript + Vite + Tailwind CSS
- Audio: pydub + ffmpeg + soundfile + noisereduce
- TTS Engines: Kokoro (primary), Chatterbox, Bark, F5-TTS, Qwen3-TTS, NeuTTS Air, Orpheus, Dia, CosyVoice2, Fish Speech, VibeVoice
- Python path: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`

## Audio Quality
- Skip aggressive noise reduction for high-quality engines (Kokoro, Chatterbox, F5-TTS, Qwen3-TTS)
- Only apply light normalization (-3dB peak) for clean TTS output
- ACX compliance: 44.1kHz, mono, 192kbps CBR MP3, -20dB RMS, -3dB peaks, -60dB noise floor

## Database
- SQLite at `data/voiceforge.db`
- Auto-migration in `seed.py` adds missing columns on startup
- Never drop/recreate tables — always ALTER TABLE ADD COLUMN

## ACX Audio Pipeline Rules

Every audio file exported from FrenzAI must pass ACX QC:
- RMS: -23dB to -18dB (target -20dB LUFS)
- True peak: below -3dB
- Noise floor: below -60dB
- Format: mono MP3, 192kbps CBR, 44.1kHz
- Silence: 400ms between sentences, 800ms between paragraphs, 1200ms between chapters
- 0.75s silence at start, 2.5s at end

After every TTS generation, run the pipeline:
1. silence_normalizer → consistent pauses
2. breath_inserter → natural breathing
3. humanizer → micro pitch/speed variations
4. add_warmth → EQ + subtle reverb (pedalboard)
5. noise_scrubber → spectral denoising (noisereduce)
6. acx_master → LUFS normalization + peak limiting (pyloudnorm)
7. acx_check → pass/fail compliance report

Never skip the mastering pipeline, even for test renders.
Libraries: pyloudnorm, pedalboard, noisereduce, pydub, soundfile, scipy

## Standalone Pipeline
- `frenzai_pipeline.py` — complete CLI pipeline for batch audiobook production
- `backend/app/services/acx_pipeline.py` — same pipeline integrated into the web app

## Common Issues
- `props.total_mem` → use `getattr(props, 'total_memory', getattr(props, 'total_mem', 0))` for PyTorch compat
- Route `/api/projects/kokoro-voices` must be defined BEFORE `/{project_id}` to avoid FastAPI path conflict
- vLLM (Orpheus dependency) may overwrite CUDA torch with CPU-only — always reinstall `torch+cu121` after
