"""Dia Engine — Multi-speaker dialogue TTS by Nari Labs."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class DiaEngine(TTSEngine):
    name = "dia"
    display_name = "Dia"
    supported_languages = ["en"]
    requires_gpu = True
    vram_required_mb = 6000
    model_size_mb = 3000
    license = "Apache-2.0"
    description = "Multi-speaker dialogue TTS by Nari Labs. Great for audiobooks with multiple characters."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)

    def is_downloaded(self) -> bool:
        try:
            import dia  # noqa: F401
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys
        # Try pip first (dia v1)
        try:
            await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "git+https://github.com/nari-labs/dia.git"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ))
        except Exception:
            # Fall back to git clone
            repo_dir = self.models_dir / "dia-repo"
            if not repo_dir.exists():
                await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.check_call(
                    ["git", "clone", "https://github.com/nari-labs/dia.git", str(repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ))
                await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                ))

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model

        def _load():
            import sys as _sys
            repo_dir = self.models_dir / "dia-repo"
            if repo_dir.exists() and str(repo_dir) not in _sys.path:
                _sys.path.insert(0, str(repo_dir))

            import os
            from dia.model import Dia
            dtype = "float32" if os.environ.get("FRENZAI_CLOUD") == "1" else "float16"
            model = Dia.from_pretrained("nari-labs/Dia-1.6B", compute_dtype=dtype)
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Dia"))

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        return np.random.randn(256).astype(np.float32)

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        def _generate():
            # Dia uses [S1] and [S2] tags for multi-speaker
            # If no tags present, wrap in [S1]
            if "[S1]" not in text and "[S2]" not in text:
                prompt = f"[S1] {text}"
            else:
                prompt = text

            output = self._model.generate(prompt, use_torch_compile=False, verbose=False)

            audio = np.array(output, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            sr = 44100  # Dia outputs at 44.1kHz
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9
            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
