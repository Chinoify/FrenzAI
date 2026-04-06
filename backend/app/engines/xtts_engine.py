"""XTTS v2 (Coqui) — Multilingual CPU TTS with voice cloning. 17 languages."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class XTTSv2Engine(TTSEngine):
    name = "xtts-v2"
    display_name = "XTTS v2 (Coqui)"
    supported_languages = [
        "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl",
        "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"
    ]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 1800
    license = "Coqui Public Model License (non-commercial)"
    description = "Battle-tested multilingual voice cloning. 17 languages. CPU-capable. Clones from 6s sample."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device)

    def is_downloaded(self) -> bool:
        try:
            from TTS.api import TTS  # noqa: F401
            return True
        except Exception:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _install():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--timeout", "300", "TTS"],
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0:
                raise RuntimeError(f"TTS (Coqui) install failed:\n{result.stderr[-1500:]}")

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            from TTS.api import TTS
            import torch
            # Auto: GPU if available, otherwise CPU
            use_gpu = torch.cuda.is_available() and self.device == "cuda"
            model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
                gpu=use_gpu,
            )
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)
        print(f"[XTTS v2] Model loaded ({self.device})", flush=True)

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import gc; gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

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
                raise ValueError("XTTS v2 requires a reference audio sample")

            # Map language codes
            lang_map = {"en-gb": "en", "zh": "zh-cn", "br": "pt"}
            lang = lang_map.get(language, language)
            if lang not in self.supported_languages:
                lang = "en"

            audio = self._model.tts(
                text=text,
                speaker_wav=ref_audio,
                language=lang,
                speed=speed,
            )

            audio = np.asarray(audio, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            sr = 24000  # XTTS v2 default

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.708

            return audio, sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
