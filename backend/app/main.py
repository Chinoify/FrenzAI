import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

# Add project root to PATH so pydub can find ffmpeg
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_root + os.pathsep + os.environ.get("PATH", "")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.seed import create_tables

# Cloud mode: all engines. Local mode: Kokoro + Chatterbox + F5-TTS + Fish Speech
IS_CLOUD = os.environ.get("FRENZAI_CLOUD") == "1"

from app.engines.builtin_engine import BuiltinEngine
from app.engines.kokoro_engine import KokoroEngine
# CPU-friendly engines (no GPU needed, no version conflicts)
from app.engines.pocket_tts_engine import PocketTTSEngine
from app.engines.neutts_engine import NeuTTSAirEngine
from app.engines.outetts_engine import OuteTTSEngine
from app.engines.xtts_engine import XTTSv2Engine
from app.engines.gpt_sovits_engine import GPTSoVITSEngine
from app.engines.registry import engine_registry
from app.routers.health import get_device
from app.routers import health as health_router
from app.routers import tts as tts_router
from app.routers import clone as clone_router
from app.routers import voices as voices_router
from app.routers import projects as projects_router
from app.routers import history as history_router
from app.routers import models as models_router
from app.routers import audio as audio_router
from app.routers import batch as batch_router
from app.routers import rvc as rvc_router
from app.routers import settings_router
from app.routers import system as system_router
from app.routers import stt as stt_router
from app.routers import s2s as s2s_router
from app.routers import acx as acx_router
from app.routers import narrator_voices as narrator_voices_router
from app.routers import characters as characters_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()

    # Register engines — CPU-friendly only (no version conflicts, work anywhere)
    device = get_device()
    engine_registry.register(BuiltinEngine(settings.models_dir, device="cpu"))
    engine_registry.register(KokoroEngine(settings.models_dir, device=device))
    engine_registry.register(PocketTTSEngine(settings.models_dir))
    engine_registry.register(NeuTTSAirEngine(settings.models_dir))
    engine_registry.register(OuteTTSEngine(settings.models_dir))
    engine_registry.register(XTTSv2Engine(settings.models_dir, device=device))
    engine_registry.register(GPTSoVITSEngine(settings.models_dir, device=device))

    # Pre-load the built-in engine so it's ready immediately
    try:
        await engine_registry.get("builtin")
        print("Built-in TTS engine loaded and ready")
    except Exception as e:
        print(f"Warning: Could not pre-load built-in engine: {e}")

    print(f"FrenzAI backend v{settings.version} started")
    print(f"Device: {device}")
    print(f"Data directory: {settings.data_dir}")
    print(f"Registered engines: {list(engine_registry.engines.keys())}")

    yield

    # Shutdown
    await engine_registry.unload_active()
    print("FrenzAI backend shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

# CORS — only allow local Electron/Vite renderer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated audio files
app.mount("/audio", StaticFiles(directory=str(settings.data_dir)), name="audio")

# Routers
app.include_router(health_router.router)
app.include_router(tts_router.router)
app.include_router(clone_router.router)
app.include_router(voices_router.router)
app.include_router(projects_router.router)
app.include_router(history_router.router)
app.include_router(models_router.router)
app.include_router(audio_router.router)
app.include_router(batch_router.router)
app.include_router(rvc_router.router)
app.include_router(settings_router.router)
app.include_router(system_router.router)
app.include_router(stt_router.router)
app.include_router(s2s_router.router)
app.include_router(acx_router.router)
app.include_router(narrator_voices_router.router)
app.include_router(characters_router.router)

# Cloud mode: serve built frontend AFTER all API routers so /api/* routes work
if IS_CLOUD:
    _frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if _frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
