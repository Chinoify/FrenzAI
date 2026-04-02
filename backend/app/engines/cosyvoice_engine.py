"""CosyVoice2 Engine — Streaming TTS with ultra-low latency and voice cloning."""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class CosyVoiceEngine(TTSEngine):
    name = "cosyvoice"
    display_name = "CosyVoice2"
    supported_languages = ["en", "zh", "ja", "ko"]
    requires_gpu = True
    vram_required_mb = 4000
    model_size_mb = 2000
    license = "Apache-2.0"
    description = "Streaming TTS by Alibaba. 150ms latency. Voice cloning. Needs git clone install."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._repo_dir = models_dir / "cosyvoice-repo"

    def is_downloaded(self) -> bool:
        if not self._repo_dir.exists() or not (self._repo_dir / "cosyvoice").exists():
            return False
        # Verify the repo's cosyvoice package is importable
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cosyvoice", str(self._repo_dir / "cosyvoice" / "__init__.py"))
            return spec is not None
        except Exception:
            return False

    async def download(self, progress_callback=None):
        def _download():
            import subprocess
            if not self._repo_dir.exists():
                subprocess.check_call(
                    ["git", "clone", "--recursive", "https://github.com/FunAudioLLM/CosyVoice.git",
                     str(self._repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            # Install requirements
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", str(self._repo_dir / "requirements.txt")],
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
            from cosyvoice.cli.cosyvoice import CosyVoice2
            model = CosyVoice2("iic/CosyVoice2-0.5B", load_jit=False, load_trt=False)
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "CosyVoice2"))

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

            audio_chunks = []
            if ref_audio:
                for chunk in self._model.inference_zero_shot(text, "", ref_audio, stream=False):
                    audio_chunks.append(chunk["tts_speech"].numpy())
            else:
                for chunk in self._model.inference_sft(text, "English Female", stream=False):
                    audio_chunks.append(chunk["tts_speech"].numpy())

            if not audio_chunks:
                return np.zeros(24000, dtype=np.float32), 24000

            audio = np.concatenate(audio_chunks)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            sr = 24000
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9
            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
