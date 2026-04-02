import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class RVCEngine(TTSEngine):
    name = "rvc"
    display_name = "RVC v2"
    supported_languages = ["any"]
    requires_gpu = True
    vram_required_mb = 2000
    model_size_mb = 400
    license = "MIT"
    description = "Real-time voice conversion (speech-to-speech). Use via Live Convert page."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "rvc"

    def is_downloaded(self) -> bool:
        # RVC is a stub — not yet implemented
        return False

    async def download(self, progress_callback=None):
        self._model_dir.mkdir(parents=True, exist_ok=True)
        (self._model_dir / "placeholder").touch()

    async def load(self) -> None:
        if self._model is not None:
            return
        self._model = {"loaded": True}

    async def unload(self) -> None:
        self._model = None

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        return np.random.randn(256).astype(np.float32)

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        # RVC is voice conversion, not TTS — use pyttsx3 as a basic fallback
        # so it doesn't crash. Users should use Live Convert for real RVC.
        import tempfile
        import soundfile as sf
        import pyttsx3

        def _generate():
            engine = pyttsx3.init()
            engine.setProperty('rate', int(engine.getProperty('rate') * speed))
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            try:
                audio, sr = sf.read(tmp_path)
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                return audio.astype(np.float32), sr
            finally:
                import os
                os.unlink(tmp_path)

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
