"""NeuTTS Air — On-device CPU TTS by Neuphonic. GGUF format, 3-sec cloning."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class NeuTTSAirEngine(TTSEngine):
    name = "neutts-air"
    display_name = "NeuTTS Air (CPU)"
    supported_languages = ["en"]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 500
    license = "Apache-2.0"
    description = "On-device TTS by Neuphonic. 0.5B params in GGUF format. Real-time on CPU. Clones from 3s sample."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device="cpu")

    def is_downloaded(self) -> bool:
        try:
            import neuphonic  # noqa: F401
            return True
        except Exception:
            try:
                import neutts  # noqa: F401
                return True
            except Exception:
                return False

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _install():
            for pkg in ["neuphonic", "neutts-air"]:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--timeout", "300", pkg],
                    capture_output=True, text=True, timeout=600,
                )
                if result.returncode == 0:
                    return
            raise RuntimeError("Failed to install NeuTTS Air pip package")

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            try:
                from neuphonic import NeuTTSAir
                return NeuTTSAir()
            except ImportError:
                from neutts import NeuTTS
                return NeuTTS()

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)
        print("[NeuTTS Air] Model loaded (CPU)", flush=True)

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import gc; gc.collect()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
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
            if not ref_audio and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:256] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and Path(decoded).exists():
                        ref_audio = decoded
                except Exception:
                    pass

            if not ref_audio:
                raise ValueError("NeuTTS Air requires a reference audio sample")

            # Try common API patterns
            try:
                result = self._model.synthesize(text=text, reference_audio=ref_audio)
            except (TypeError, AttributeError):
                try:
                    result = self._model.generate(text=text, ref_audio=ref_audio)
                except (TypeError, AttributeError):
                    result = self._model(text, ref_audio)

            # Result could be (audio, sr), audio, or dict
            if isinstance(result, tuple):
                audio, sr = result[0], result[1] if len(result) > 1 else 22050
            elif isinstance(result, dict):
                audio = result.get("audio") or result.get("samples")
                sr = result.get("sample_rate") or result.get("sr") or 22050
            else:
                audio = result
                sr = 22050

            if hasattr(audio, "numpy"):
                audio = audio.numpy()
            audio = np.asarray(audio, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.708
            return audio, sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
