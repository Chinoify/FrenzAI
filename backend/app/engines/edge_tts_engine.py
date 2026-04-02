"""Edge TTS Engine — 400+ free Microsoft neural voices via edge-tts library."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class EdgeTTSEngine(TTSEngine):
    name = "edge-tts"
    display_name = "Edge TTS (Microsoft)"
    supported_languages = [
        "en", "en-gb", "de", "fr", "es", "it", "pt", "hi", "ja", "ko",
        "zh", "ar", "ru", "nl", "pl", "sv", "tr", "id", "th", "vi",
    ]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 0
    license = "Free (Microsoft Edge)"
    description = "400+ free Microsoft neural voices. No GPU needed. Requires internet. Great for audiobook narration."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device)

    def is_downloaded(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "edge-tts"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ),
        )

    async def load(self) -> None:
        import edge_tts
        self._model = True  # No model to load — edge-tts is an API client

    async def unload(self) -> None:
        self._model = None

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        # Edge TTS doesn't support voice cloning — return empty
        return np.zeros(256, dtype=np.float32)

    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        import edge_tts
        import tempfile
        import soundfile as sf

        # Get voice name from kwargs or use default
        edge_voice = kwargs.get("edge_voice") or kwargs.get("kokoro_voice")
        if not edge_voice:
            # Try to decode from embedding
            if voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:100] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and "Neural" in decoded:
                        edge_voice = decoded
                except Exception:
                    pass

        if not edge_voice:
            edge_voice = "en-US-AvaNeural"  # Best default for audiobooks

        # Speed: edge-tts uses percentage like "+20%" or "-10%"
        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"

        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)

        # Generate to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)

        # Convert MP3 to numpy array
        from pydub import AudioSegment
        audio_seg = AudioSegment.from_mp3(tmp_path)
        samples = np.array(audio_seg.get_array_of_samples(), dtype=np.float32)
        samples = samples / (2 ** (audio_seg.sample_width * 8 - 1))
        sr = audio_seg.frame_rate

        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)

        # Normalize
        peak = np.abs(samples).max()
        if peak > 0:
            samples = samples / peak * 0.9

        return samples.astype(np.float32), sr

    async def list_voices(self) -> list[dict]:
        """Return all available Edge TTS voices."""
        import edge_tts
        voices = await edge_tts.list_voices()
        return [
            {
                "code": v["ShortName"],
                "name": v.get("FriendlyName", v["ShortName"]),
                "language": v["Locale"],
                "gender": v.get("Gender", "Unknown").lower(),
            }
            for v in voices
        ]
