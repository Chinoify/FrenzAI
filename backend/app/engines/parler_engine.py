import asyncio
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine

# Fix espeak-ng data path for Parler's phonemizer dependency
try:
    import espeakng_loader
    _espeak_dir = str(Path(espeakng_loader.__file__).parent)
    os.environ.setdefault('PHONEMIZER_ESPEAK_LIBRARY', str(Path(_espeak_dir) / 'espeak-ng.dll'))
    os.environ.setdefault('PHONEMIZER_ESPEAK_DATA', str(Path(_espeak_dir) / 'espeak-ng-data'))
    os.environ.setdefault('ESPEAK_DATA_PATH', str(Path(_espeak_dir) / 'espeak-ng-data'))
except ImportError:
    pass

import os as _os
# Use large model on cloud (better quality), mini locally (fits in VRAM)
MODEL_REPO = "parler-tts/parler-tts-large-v1" if _os.environ.get("FRENZAI_CLOUD") == "1" else "parler-tts/parler-tts-mini-v1.1"

DEFAULT_VOICE_DESCRIPTION = (
    "A female speaker with a clear voice delivers a speech naturally"
)


class ParlerEngine(TTSEngine):
    name = "parler"
    display_name = "Parler-TTS"
    supported_languages = ["en"]
    requires_gpu = True
    vram_required_mb = 1800
    model_size_mb = 1600
    license = "Apache-2.0"
    description = (
        "Create voices from text descriptions. 880M params. "
        "'A warm female narrator with British accent.'"
    )

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "parler-tts-mini-v1.1"
        self._tokenizer = None

    def is_downloaded(self) -> bool:
        # Check pip package is importable
        try:
            import parler_tts  # noqa: F401
        except ImportError:
            return False
        # Check model weights are on disk
        config_path = self._model_dir / "config.json"
        return config_path.exists()

    async def download(self, progress_callback=None):
        import subprocess, sys

        def _pip(args, label="pip"):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--timeout", "300"] + args,
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{label} failed:\n{result.stderr[-1500:]}")

        def _download():
            # Step 1: Install parler-tts + deps without pulling full dep tree
            _pip(["--no-deps", "parler-tts", "espeakng-loader"], "parler-tts")
            if progress_callback:
                progress_callback(20)
            _pip([
                "--no-deps", "descript-audio-codec", "descript-audiotools",
                "flatten-dict", "julius", "importlib_resources",
                "docstring_parser", "randomname",
            ], "parler-tts audio deps")
            if progress_callback:
                progress_callback(35)
            _pip(["tensorboard", "transformers==4.57.3"], "tensorboard + transformers")
            if progress_callback:
                progress_callback(50)

            # Step 2: Download model weights from HuggingFace
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id=MODEL_REPO,
                local_dir=str(self._model_dir),
                ignore_patterns=["*.md", "*.txt"],
            )
            if progress_callback:
                progress_callback(90)

            # Step 3: Ensure CUDA torch is still intact
            _pip([
                "--force-reinstall", "--no-deps",
                "torch", "torchaudio", "--index-url",
                "https://download.pytorch.org/whl/cu121",
            ], "CUDA torch fix")

        await asyncio.get_event_loop().run_in_executor(None, _download)

    async def load(self) -> None:
        if self._model is not None:
            return

        from app.engines.vram_utils import safe_load_model

        def _load():
            import torch
            from transformers import AutoTokenizer
            from parler_tts import ParlerTTSForConditionalGeneration

            tokenizer = AutoTokenizer.from_pretrained(str(self._model_dir))
            import os
            use_fp16 = os.environ.get("FRENZAI_CLOUD") != "1"
            model = ParlerTTSForConditionalGeneration.from_pretrained(
                str(self._model_dir),
                torch_dtype=torch.float16 if use_fp16 else torch.float32,
                device_map="auto",
            )
            return model, tokenizer

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Parler-TTS"))
        self._model, self._tokenizer = result

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        """Parler uses text descriptions instead of voice embeddings.
        Return a dummy embedding — voice is controlled via voice_description kwarg."""
        return np.zeros(256, dtype=np.float32)

    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        def _generate():
            import torch

            voice_description = kwargs.get(
                "voice_description", DEFAULT_VOICE_DESCRIPTION
            )

            # Tokenize the voice description
            description_tokens = self._tokenizer(
                voice_description, return_tensors="pt"
            )

            # Tokenize the text to speak
            prompt_tokens = self._tokenizer(
                text, return_tensors="pt"
            )

            # Move inputs to model device
            model_device = next(self._model.parameters()).device
            input_ids = description_tokens.input_ids.to(model_device)
            attention_mask = description_tokens.attention_mask.to(model_device)
            prompt_input_ids = prompt_tokens.input_ids.to(model_device)
            prompt_attention_mask = prompt_tokens.attention_mask.to(model_device)

            # Generate audio
            with torch.no_grad():
                generation = self._model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    prompt_input_ids=prompt_input_ids,
                    prompt_attention_mask=prompt_attention_mask,
                )

            audio_array = generation.cpu().numpy().squeeze()
            sr = self._model.config.sampling_rate

            # Normalize to -3dB peak
            peak = np.abs(audio_array).max()
            if peak > 0:
                target_peak = 10 ** (-3.0 / 20.0)  # ~0.708
                audio_array = audio_array / peak * target_peak

            return audio_array.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
