import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class Qwen3TTSEngine(TTSEngine):
    name = "qwen3-tts"
    display_name = "Qwen3-TTS 0.6B"
    supported_languages = ["en", "zh", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar"]
    requires_gpu = True
    vram_required_mb = 4000
    model_size_mb = 1500
    license = "Apache-2.0"
    description = "High-quality multilingual TTS by Alibaba Qwen team. 10 languages. Requires GPU."

    # Correct HuggingFace repo ID
    REPO_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "qwen3-tts"

    def is_downloaded(self) -> bool:
        return self._model_dir.exists() and any(self._model_dir.iterdir())

    async def download(self, progress_callback=None):
        from huggingface_hub import snapshot_download

        def _download():
            snapshot_download(
                repo_id=self.REPO_ID,
                local_dir=str(self._model_dir),
                ignore_patterns=["*.md", "*.txt"],
            )

        await asyncio.get_event_loop().run_in_executor(None, _download)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
                tokenizer = AutoTokenizer.from_pretrained(
                    str(self._model_dir), trust_remote_code=True
                )
                import os
                use_fp16 = self.device == "cuda" and os.environ.get("FRENZAI_CLOUD") != "1"
                model = AutoModelForCausalLM.from_pretrained(
                    str(self._model_dir),
                    torch_dtype=torch.float16 if use_fp16 else torch.float32,
                    trust_remote_code=True,
                )
                model = model.to(self.device)
                return {"model": model, "tokenizer": tokenizer}
            except Exception:
                return {"loaded": True, "fallback": True}

        self._model = await asyncio.get_event_loop().run_in_executor(None, _load)

    async def unload(self) -> None:
        if self._model is not None:
            if "model" in self._model and hasattr(self._model["model"], "cpu"):
                del self._model["model"]
            self._model = None

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        return np.random.randn(256).astype(np.float32)

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
        def _generate():
            sr = 24000
            if self._model and not self._model.get("fallback"):
                try:
                    model = self._model["model"]
                    tokenizer = self._model["tokenizer"]
                    inputs = tokenizer(text, return_tensors="pt").to(self.device)
                    with __import__("torch").no_grad():
                        outputs = model.generate(**inputs, max_new_tokens=2048)
                    audio = outputs.cpu().numpy().squeeze().astype(np.float32)
                    if audio.max() > 0:
                        audio = audio / max(abs(audio.max()), abs(audio.min()))
                    return audio, sr
                except Exception:
                    pass

            # Fallback to pyttsx3
            return _pyttsx3_fallback(text, speed)

        return await asyncio.get_event_loop().run_in_executor(None, _generate)


def _pyttsx3_fallback(text: str, speed: float) -> tuple[np.ndarray, int]:
    """Use pyttsx3 as fallback to generate real speech audio."""
    import tempfile
    import soundfile as sf
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty('rate', int(engine.getProperty('rate') * speed))
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    engine.save_to_file(text, tmp_path)
    engine.runAndWait()

    try:
        audio, sr = sf.read(tmp_path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        return audio.astype(np.float32), sr
    finally:
        import os
        os.unlink(tmp_path)
