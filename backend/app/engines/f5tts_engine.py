"""F5-TTS Engine — Flow-matching TTS with zero-shot voice cloning."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class F5TTSEngine(TTSEngine):
    name = "f5tts"
    display_name = "F5-TTS"
    supported_languages = ["en", "zh"]
    requires_gpu = True
    vram_required_mb = 6000
    model_size_mb = 1200
    license = "MIT"
    description = "Flow-matching TTS with zero-shot voice cloning. 335M params. Needs ~6GB VRAM."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)

    def is_downloaded(self) -> bool:
        try:
            import f5_tts  # noqa: F401
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _pip(args, label="pip"):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--timeout", "300"] + args,
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{label} failed:\n{result.stderr[-1500:]}")

        def _install():
            # Install f5-tts without deps to avoid overwriting CUDA torch
            _pip(["--no-deps", "f5-tts"], "f5-tts")
            if progress_callback:
                progress_callback(30)
            # Install only the runtime deps f5-tts actually needs for inference
            _pip([
                "accelerate", "safetensors", "transformers==4.57.3", "vocos",
                "torchdiffeq", "einops", "x_transformers", "cached_path",
                "pypinyin", "rjieba", "unidecode", "tomli", "librosa",
                "hydra-core", "omegaconf", "ema_pytorch", "bitsandbytes",
            ], "f5-tts deps")
            if progress_callback:
                progress_callback(80)
            # Ensure CUDA torch is still intact
            _pip([
                "--force-reinstall", "--no-deps",
                "torch", "torchaudio", "--index-url",
                "https://download.pytorch.org/whl/cu121",
            ], "CUDA torch fix")

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model, cleanup_vram

        def _load():
            import torch
            from f5_tts.api import F5TTS
            model = F5TTS(model_type="F5-TTS", device=self.device)
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "F5-TTS"))

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        # F5-TTS uses reference audio directly, not embeddings
        # Store the path as bytes in the embedding array
        path_bytes = audio_path.encode("utf-8")
        embedding = np.zeros(256, dtype=np.float32)
        for i, b in enumerate(path_bytes[:256]):
            embedding[i] = float(b)
        return embedding

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        def _generate():
            ref_audio = kwargs.get("sample_path")

            # Decode ref audio path from embedding if no sample_path
            if not ref_audio and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:256] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and Path(decoded).exists():
                        ref_audio = decoded
                except Exception:
                    pass

            if ref_audio:
                audio, sr, _ = self._model.infer(
                    ref_file=ref_audio,
                    ref_text="",
                    gen_text=text,
                    speed=speed,
                )
            else:
                audio, sr, _ = self._model.infer(
                    ref_file="",
                    ref_text="",
                    gen_text=text,
                    speed=speed,
                )

            if isinstance(audio, np.ndarray):
                pass
            else:
                audio = audio.cpu().numpy()

            if len(audio.shape) > 1:
                audio = audio.squeeze()

            # Normalize
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9

            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
