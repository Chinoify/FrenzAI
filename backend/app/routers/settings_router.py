"""Settings API — persist and retrieve app configuration."""
import json
from pathlib import Path

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_FILE = settings.data_dir / "settings.json"

DEFAULT_SETTINGS = {
    # General
    "theme": "dark",
    "font_size": "medium",
    "compact_mode": False,
    "auto_save_interval": 60,
    "startup_page": "/",
    "notification_generation_complete": True,
    "notification_errors": True,
    "notification_sound": True,
    "notification_volume": 80,

    # Audio Engine
    "active_tts_model": "kokoro",
    "generation_quality": "standard",
    "default_temperature": 0.7,
    "default_seed": None,
    "random_seed": True,
    "max_tokens_per_chunk": 300,
    "batch_size": 3,
    "fallback_model": "builtin",
    "active_stt_model": "base",
    "stt_language": "auto",
    "stt_word_timestamps": True,
    "stt_vad_filter": True,
    "stt_beam_size": 5,

    # Voice & Cloning
    "default_stability": 70,
    "default_similarity": 80,
    "default_style": 50,
    "default_speed": 1.0,
    "min_reference_length": 30,
    "auto_enhance_reference": True,
    "save_original_reference": True,

    # ACX & Audiobook
    "acx_rms_target": -20.0,
    "acx_peak_max": -3.0,
    "acx_noise_max": -60.0,
    "acx_bitrate": "192k",
    "noise_scrubber_enabled": True,
    "noise_scrubber_strength": 75,
    "warmth_eq_enabled": True,
    "warmth_low_shelf_db": 1.5,
    "warmth_high_shelf_db": -2.0,
    "warmth_presence_db": 0,
    "compression_enabled": True,
    "compression_threshold": -20,
    "compression_ratio": "2:1",
    "reverb_enabled": True,
    "reverb_room_size": 10,
    "reverb_wet_level": 5,
    "humanizer_enabled": True,
    "humanizer_speed_variation": 3,
    "humanizer_volume_variation": 1.5,
    "humanizer_pause_min": 50,
    "humanizer_pause_max": 150,
    "breath_enabled": True,
    "breath_threshold_words": 15,
    "breath_min_ms": 80,
    "breath_max_ms": 130,
    "breath_volume_db": -15,
    "opening_credits_template": "{title}. Written by {author}. Narrated by {narrator}.",
    "closing_credits_template": "End of {title}. Written by {author}. The End.",
    "chapter_filename_format": "01_Chapter_One",
    "max_parallel_chapters": 2,
    "auto_retry_failed": True,
    "max_retries": 3,
    "continue_on_error": True,

    # Storage
    "output_dir": str(settings.exports_dir),
    "cache_dir": str(settings.data_dir / "cache"),
    "cache_size_limit_gb": 10,
    "cache_auto_clear_days": 30,
    "auto_delete_temp": True,
    "history_keep_days": 90,
    "history_max_entries": 500,
    "history_include_audio": True,

    # GPU & Performance
    "vram_warn_threshold": 85,
    "vram_critical_threshold": 92,
    "auto_flush_vram": True,
    "compute_precision": "float16",
    "force_cpu": False,
    "parallel_threads": 3,
    "chunk_cache_enabled": True,
    "preload_model": False,
    "show_vram_in_header": True,
    "show_cpu_in_header": False,

    # Accessibility
    "reduce_motion": False,
    "high_contrast": False,
    "text_scaling": 100,
    "waveform_style": "bars",
    "color_theme": "purple",

    # Developer
    "developer_mode": False,
    "log_level": "INFO",
    "api_request_log": False,
}


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = {**DEFAULT_SETTINGS, **saved}
            return merged
        except Exception:
            pass
    return {**DEFAULT_SETTINGS}


def _save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("")
async def get_settings():
    """Return full settings object."""
    return _load_settings()


@router.post("/save")
async def save_settings(updates: dict):
    """Merge partial updates into settings."""
    current = _load_settings()
    current.update(updates)
    _save_settings(current)
    return {"saved": True}


@router.post("/reset")
async def reset_settings():
    """Reset all settings to defaults."""
    _save_settings(DEFAULT_SETTINGS)
    return {"reset": True, "settings": DEFAULT_SETTINGS}
