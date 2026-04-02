"""VibeVoice Engine — Microsoft's high-quality TTS with voice cloning."""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class VibeVoiceEngine(TTSEngine):
    name = "vibevoice"
    display_name = "VibeVoice"
    supported_languages = ["en", "zh"]
    requires_gpu = True
    vram_required_mb = 8000
    model_size_mb = 3000
    license = "MIT"
    description = "High-quality TTS by Microsoft (community fork). 1.5B params. Voice cloning. Needs ~8GB VRAM."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._repo_dir = models_dir / "vibevoice-repo"

    def is_downloaded(self) -> bool:
        if not self._repo_dir.exists():
            return False
        try:
            import vibevoice  # noqa: F401
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        def _download():
            import subprocess
            if not self._repo_dir.exists():
                subprocess.check_call(
                    ["git", "clone", "https://github.com/vibevoice-community/VibeVoice.git",
                     str(self._repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            # Install
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
            import torch
            if str(self._repo_dir) not in sys.path:
                sys.path.insert(0, str(self._repo_dir))
            from vibevoice import VibeVoice
            import os
            use_fp16 = os.environ.get("FRENZAI_CLOUD") != "1"
            model = VibeVoice.from_pretrained(
                "microsoft/VibeVoice-1.5B",
                device=self.device,
                torch_dtype=torch.float16 if use_fp16 else torch.float32,
            )
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "VibeVoice"))

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

            if ref_audio:
                audio, sr = self._model.synthesize(text=text, ref_audio=ref_audio)
            else:
                audio, sr = self._model.synthesize(text=text)

            if not isinstance(audio, np.ndarray):
                audio = audio.cpu().numpy()
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9
            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
