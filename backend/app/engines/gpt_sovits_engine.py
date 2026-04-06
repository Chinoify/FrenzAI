"""GPT-SoVITS v2 Pro — Few-shot voice cloning. 1 minute training, 5s zero-shot."""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class GPTSoVITSEngine(TTSEngine):
    name = "gpt-sovits"
    display_name = "GPT-SoVITS v2"
    supported_languages = ["en", "zh", "ja", "ko"]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 2000
    license = "MIT"
    description = "Few-shot voice cloning. 1 min training or 5s zero-shot. CPU RTF 0.526 on M4."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device)
        self._repo_dir = models_dir / "gpt-sovits-repo"

    def is_downloaded(self) -> bool:
        return self._repo_dir.exists() and (self._repo_dir / "GPT_SoVITS").exists()

    async def download(self, progress_callback=None):
        import subprocess

        def _download():
            if not self._repo_dir.exists():
                subprocess.check_call(
                    ["git", "clone", "--depth", "1",
                     "https://github.com/RVC-Boss/GPT-SoVITS.git",
                     str(self._repo_dir)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )

        await asyncio.get_event_loop().run_in_executor(None, _download)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            if str(self._repo_dir) not in sys.path:
                sys.path.insert(0, str(self._repo_dir))
            try:
                from GPT_SoVITS.inference_webui import get_tts_wav
                return {"infer": get_tts_wav}
            except ImportError:
                return {"infer": None, "fallback": True}

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)
        print("[GPT-SoVITS] Model loaded", flush=True)

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
                raise ValueError("GPT-SoVITS requires a reference audio sample")

            infer = self._model.get("infer")
            if infer is None:
                raise RuntimeError("GPT-SoVITS not properly loaded")

            result = infer(
                ref_wav_path=ref_audio,
                prompt_text="",
                prompt_language=language,
                text=text,
                text_language=language,
                speed=speed,
            )

            if isinstance(result, tuple) and len(result) == 2:
                sr, audio = result
            else:
                audio, sr = result, 32000

            audio = np.asarray(audio, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.708

            return audio, sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
