import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class BarkEngine(TTSEngine):
    name = "bark"
    display_name = "Bark"
    supported_languages = ["en", "zh", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar",
                           "it", "hi", "pl"]
    requires_gpu = True
    vram_required_mb = 4000
    model_size_mb = 5000
    license = "MIT"
    description = "Expressive TTS with emotions, laughter, music. 13 languages. Slower but creative."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "bark"
        self._processor = None

    def is_downloaded(self) -> bool:
        return self._model_dir.exists() and any(self._model_dir.iterdir())

    async def download(self, progress_callback=None):
        from huggingface_hub import snapshot_download
        await asyncio.get_event_loop().run_in_executor(None, lambda: snapshot_download(
            repo_id="suno/bark", local_dir=str(self._model_dir),
            ignore_patterns=["*.md", "*.txt"],
        ))

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model

        def _load():
            from transformers import BarkModel, AutoProcessor
            import os, torch
            processor = AutoProcessor.from_pretrained(str(self._model_dir))
            # Full fp32 on cloud, fp16 locally to save VRAM
            use_fp16 = self.device == "cuda" and os.environ.get("FRENZAI_CLOUD") != "1"
            model = BarkModel.from_pretrained(
                str(self._model_dir),
                torch_dtype=torch.float16 if use_fp16 else torch.float32,
            )
            model = model.to(self.device)
            return model, processor

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Bark"))
        self._model, self._processor = result

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            del self._processor
            self._model = None
            self._processor = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        return np.random.randn(256).astype(np.float32)

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        def _generate():
            voice_preset = f"v2/{language}_speaker_1"
            inputs = self._processor(text, voice_preset=voice_preset)
            # Move inputs to device
            inputs = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in inputs.items()}
            audio_array = self._model.generate(**inputs)
            audio_array = audio_array.cpu().numpy().squeeze()
            sr = self._model.generation_config.sample_rate
            # Normalize
            if audio_array.max() > 0:
                audio_array = audio_array / max(abs(audio_array.max()), abs(audio_array.min()))
            return audio_array.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
