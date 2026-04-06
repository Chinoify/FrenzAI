"""Pocket TTS — CPU-native TTS by Kyutai. Runs on CPU at 6x real-time."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class PocketTTSEngine(TTSEngine):
    name = "pocket-tts"
    display_name = "Pocket TTS (CPU)"
    supported_languages = ["en"]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 400
    license = "MIT"
    description = "CPU-native voice cloning by Kyutai. 100M params. 6x real-time on 2 CPU cores. Clones from 5s sample."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device="cpu")  # always CPU

    def is_downloaded(self) -> bool:
        try:
            import pocket_tts  # noqa: F401
            return True
        except Exception:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _install():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--timeout", "300", "pocket-tts"],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"pocket-tts install failed:\n{result.stderr[-1500:]}")

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            from pocket_tts import TTSModel
            model = TTSModel.load_model()
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)
        print("[Pocket TTS] Model loaded (CPU)", flush=True)

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import gc; gc.collect()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        # Pocket TTS uses reference audio path directly
        path_bytes = audio_path.encode("utf-8")
        embedding = np.zeros(256, dtype=np.float32)
        for i, b in enumerate(path_bytes[:256]):
            embedding[i] = float(b)
        return embedding

    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        def _generate():
            ref_audio = kwargs.get("sample_path")

            # Decode path from embedding if no sample_path
            if not ref_audio and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:256] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and Path(decoded).exists():
                        ref_audio = decoded
                except Exception:
                    pass

            if not ref_audio:
                raise ValueError("Pocket TTS requires a reference audio sample")

            # Cache voice state per reference path for speed
            if not hasattr(self, "_voice_states"):
                self._voice_states = {}
            if ref_audio not in self._voice_states:
                self._voice_states[ref_audio] = self._model.get_state_for_audio_prompt(ref_audio)
            voice_state = self._voice_states[ref_audio]

            audio_tensor = self._model.generate_audio(voice_state, text)
            audio = audio_tensor.numpy().astype(np.float32) if hasattr(audio_tensor, "numpy") else np.asarray(audio_tensor, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            sr = self._model.sample_rate

            # Normalize to -3dB
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.708

            return audio, sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
