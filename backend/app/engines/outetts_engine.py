"""OuteTTS — CPU TTS via llama.cpp by OuteAI. JSON voice profiles."""
import asyncio
import json
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class OuteTTSEngine(TTSEngine):
    name = "outetts"
    display_name = "OuteTTS (CPU)"
    supported_languages = ["en", "zh", "ja", "ko"]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 800
    license = "MIT"
    description = "CPU TTS via llama.cpp. Zero-shot cloning with portable JSON speaker profiles."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device="cpu")
        self._speaker_cache = {}

    def is_downloaded(self) -> bool:
        try:
            import outetts  # noqa: F401
            return True
        except Exception:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _install():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--timeout", "300", "outetts"],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(f"outetts install failed:\n{result.stderr[-1500:]}")

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            import outetts
            try:
                cfg = outetts.HFModelConfig_v2(
                    model_path="OuteAI/OuteTTS-0.3-1B",
                    tokenizer_path="OuteAI/OuteTTS-0.3-1B",
                )
                model = outetts.InterfaceHF(model_version="0.3", cfg=cfg)
            except Exception:
                model = outetts.Interface(config=outetts.ModelConfig.auto_config(
                    model="OuteAI/OuteTTS-0.3-1B",
                    backend=outetts.Backend.HF,
                ))
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)
        print("[OuteTTS] Model loaded (CPU)", flush=True)

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            self._speaker_cache.clear()
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

            # Get or create speaker profile
            speaker = None
            if ref_audio:
                if ref_audio not in self._speaker_cache:
                    self._speaker_cache[ref_audio] = self._model.create_speaker(audio_path=ref_audio)
                speaker = self._speaker_cache[ref_audio]

            output = self._model.generate(
                text=text,
                temperature=0.4,
                repetition_penalty=1.1,
                max_length=4096,
                speaker=speaker,
            )

            audio = output.audio if hasattr(output, "audio") else output
            sr = getattr(output, "sample_rate", 24000) if hasattr(output, "sample_rate") else 24000

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
