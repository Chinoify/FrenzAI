"""Fish Speech Engine — High-quality multilingual TTS with DualAR architecture."""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class FishSpeechEngine(TTSEngine):
    name = "fishspeech"
    display_name = "Fish Speech"
    supported_languages = ["en", "zh", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar"]
    requires_gpu = True
    vram_required_mb = 8000
    model_size_mb = 4000
    license = "Fish Audio Research License"
    description = "Top-ranked open TTS by Fish Audio. DualAR architecture. 10+ languages. Needs ~8GB VRAM."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._repo_dir = models_dir / "fish-speech"

    def is_downloaded(self) -> bool:
        try:
            import fish_speech  # noqa: F401
        except ImportError:
            return False
        if not self._repo_dir.exists():
            return False
        has_weights = any(self._repo_dir.glob("*.pth")) or any(self._repo_dir.glob("*.safetensors"))
        has_source = (self._repo_dir / "fish_speech").exists() or (self._repo_dir / "setup.py").exists()
        return has_weights or has_source

    async def download(self, progress_callback=None):
        def _download():
            import subprocess
            if not self._repo_dir.exists():
                subprocess.check_call(
                    ["git", "clone", "https://github.com/fishaudio/fish-speech.git",
                     str(self._repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-e", str(self._repo_dir)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

        await asyncio.get_event_loop().run_in_executor(None, _download)

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model

        def _load():
            if str(self._repo_dir) not in sys.path:
                sys.path.insert(0, str(self._repo_dir))
            from fish_speech.inference import TTSInference
            model = TTSInference(device=self.device)
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Fish Speech"))

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        path_bytes = audio_path.encode("utf-8")
        embedding = np.zeros(256, dtype=np.float32)
        for i, b in enumerate(path_bytes[:256]):
            embedding[i] = float(b)
        return embedding

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        def _generate():
            ref_audio = kwargs.get("sample_path")

            if not ref_audio and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:256] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and Path(decoded).exists():
                        ref_audio = decoded
                except Exception:
                    pass

            audio, sr = self._model.synthesize(
                text=text,
                ref_audio=ref_audio,
                language=language,
            )

            if not isinstance(audio, np.ndarray):
                audio = audio.cpu().numpy()
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9
            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
