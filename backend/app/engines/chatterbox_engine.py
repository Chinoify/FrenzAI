"""Chatterbox TTS Engine — SoTA voice cloning by Resemble AI."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class ChatterboxEngine(TTSEngine):
    name = "chatterbox"
    display_name = "Chatterbox"
    supported_languages = ["en", "zh", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar",
                           "it", "nl", "pl", "sv", "da", "no", "fi", "tr", "vi", "th",
                           "id", "hi", "uk"]
    requires_gpu = True
    vram_required_mb = 3000
    model_size_mb = 2800
    license = "MIT"
    description = "SoTA open-source TTS by Resemble AI. Voice cloning from any audio sample. 23 languages."

    REPO_ID = "ResembleAI/chatterbox"

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "chatterbox"

    def is_downloaded(self) -> bool:
        # Chatterbox downloads on first use via from_pretrained()
        try:
            import chatterbox
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        import subprocess, sys
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "chatterbox-tts"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ),
        )

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model

        def _load():
            import os, torch
            from chatterbox.tts import ChatterboxTTS
            model = ChatterboxTTS.from_pretrained(device=self.device)
            # fp16 only on local (low VRAM); cloud uses full fp32 quality
            if self.device == "cuda" and os.environ.get("FRENZAI_CLOUD") != "1":
                try:
                    model.half()
                    print("[Chatterbox] Loaded in fp16 (low VRAM mode)", flush=True)
                except Exception:
                    pass
            else:
                print("[Chatterbox] Loaded in fp32 (full quality)", flush=True)
            return {"model": model, "sr": model.sr}

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Chatterbox"))

    async def unload(self) -> None:
        if self._model is not None:
            if "model" in self._model:
                del self._model["model"]
            self._model = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        """Store the audio path in the embedding for later retrieval."""
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
            model = self._model["model"]
            sr = self._model["sr"]

            # Get voice reference audio for cloning
            audio_prompt_path = kwargs.get("sample_path")

            # Try to recover path from embedding if no sample_path
            if not audio_prompt_path and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:256] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and Path(decoded).exists():
                        audio_prompt_path = decoded
                except Exception:
                    pass

            # Generate with voice cloning if we have a reference
            wav = model.generate(
                text,
                audio_prompt_path=audio_prompt_path,
                exaggeration=0.5,
                cfg_weight=0.5,
                temperature=0.8,
            )

            audio = wav.cpu().numpy().squeeze().astype(np.float32)

            # Normalize
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9

            return audio, sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
