"""Qwen3-TTS Engine — Instructable TTS with voice cloning and emotion control."""
import asyncio
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine


class Qwen3TTSEngine(TTSEngine):
    name = "qwen3tts"
    display_name = "Qwen3-TTS"
    supported_languages = ["en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"]
    requires_gpu = True
    vram_required_mb = 6000
    model_size_mb = 2500
    license = "Apache-2.0"
    description = "Instructable TTS by Alibaba. 0.6B params. Voice cloning from 3s audio. Natural language emotion control."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)

    def is_downloaded(self) -> bool:
        try:
            import qwen_tts  # noqa: F401
            return True
        except Exception:
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
            # Install qwen-tts without deps — it pins transformers==4.57.3 which breaks everything
            _pip(["--no-deps", "qwen-tts"], "qwen-tts")
            if progress_callback:
                progress_callback(30)
            # Install only the runtime deps needed for inference
            _pip(["onnxruntime", "accelerate", "safetensors", "transformers==4.57.3"], "qwen-tts deps")
            if progress_callback:
                progress_callback(60)
            # Create sox stub if SoX binary not available (only needed for tokenizer training)
            site_pkg = subprocess.run(
                [sys.executable, "-c", "import site; print(site.getsitepackages()[-1])"],
                capture_output=True, text=True,
            ).stdout.strip()
            sox_stub = Path(site_pkg) / "sox.py"
            if not sox_stub.exists():
                sox_stub.write_text(
                    '"""Stub sox module."""\n'
                    'class Transformer:\n'
                    '    def __init__(self, *a, **kw): pass\n'
                    '    def build(self, *a, **kw): return self\n'
                )
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

        from app.engines.vram_utils import safe_load_model

        def _load():
            import os, torch
            from qwen_tts import Qwen3TTS
            use_fp16 = os.environ.get("FRENZAI_CLOUD") != "1"
            model = Qwen3TTS(
                model_name="Qwen/Qwen3-TTS-12Hz-0.6B",
                device=self.device,
                torch_dtype=torch.float16 if use_fp16 else torch.float32,
            )
            return model

        self._model = await asyncio.get_event_loop().run_in_executor(
            None, lambda: safe_load_model(_load, "Qwen3-TTS"))

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            from app.engines.vram_utils import cleanup_vram
            cleanup_vram()

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        path_bytes = audio_path.encode("utf-8")
        embedding = np.zeros(256, dtype=np.float32)
        for i, b in enumerate(path_bytes[:256]):
            embedding[i] = float(b)
        return embedding

    async def generate(self, text: str, voice_embedding: Optional[np.ndarray] = None,
                       language: str = "en", speed: float = 1.0, **kwargs) -> tuple[np.ndarray, int]:
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

            generate_kwargs = {
                "text": text,
                "speed": speed,
            }

            if ref_audio:
                generate_kwargs["ref_audio"] = ref_audio

            audio, sr = self._model.generate(**generate_kwargs)

            if not isinstance(audio, np.ndarray):
                audio = audio.cpu().numpy()
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9
            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
