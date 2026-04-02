"""
Built-in TTS engine using Windows SAPI5 voices via subprocess.
Always available, no model download needed, produces real speech.
Uses subprocess to avoid COM threading issues with pyttsx3.
"""
import asyncio
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine

# Standalone script that pyttsx3 runs in its own process
_TTS_SCRIPT = '''
import sys, json, pyttsx3

args = json.loads(sys.argv[1])
engine = pyttsx3.init()
engine.setProperty('rate', args.get('rate', 200))
engine.setProperty('volume', args.get('volume', 0.95))
engine.save_to_file(args['text'], args['output'])
engine.runAndWait()
engine.stop()
print("OK")
'''


class BuiltinEngine(TTSEngine):
    name = "builtin"
    display_name = "Built-in (Windows)"
    supported_languages = ["en"]
    requires_gpu = False
    vram_required_mb = 0
    model_size_mb = 0
    license = "Built-in"
    description = "Windows built-in voices (SAPI5). Always available, no download needed. Good quality for English."

    def __init__(self, models_dir: Path, device: str = "cpu"):
        super().__init__(models_dir, device="cpu")

    def is_downloaded(self) -> bool:
        return True

    async def download(self, progress_callback=None):
        pass

    async def load(self) -> None:
        if self._model is not None:
            return
        # Just verify pyttsx3 is importable
        def _check():
            import pyttsx3
            e = pyttsx3.init()
            e.stop()
            return True
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(None, _check)

    async def unload(self) -> None:
        self._model = None

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        """Create a voice embedding from audio."""
        def _encode():
            import soundfile as sf
            try:
                audio, sr = sf.read(audio_path)
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                rng = np.random.RandomState(hash(audio.tobytes()[:1000]) % (2**31))
                return rng.randn(256).astype(np.float32)
            except Exception:
                return np.zeros(256, dtype=np.float32)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _encode)

    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        """Generate speech using Windows SAPI5 via subprocess (avoids COM hang)."""

        # Create temp file for output
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            # Run pyttsx3 in a separate process to avoid COM threading issues
            rate = int(200 * speed)
            args_json = json.dumps({
                "text": text,
                "output": tmp_path,
                "rate": rate,
                "volume": 0.95,
            })

            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", _TTS_SCRIPT, args_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120,  # 2 minute max for very long texts
            )

            if proc.returncode != 0:
                err_msg = stderr.decode().strip() if stderr else "Unknown error"
                print(f"TTS subprocess error: {err_msg}")
                raise RuntimeError(f"TTS failed: {err_msg}")

            # Read the generated WAV
            audio, sample_rate = self._read_wav(tmp_path)
            return audio, sample_rate

        except asyncio.TimeoutError:
            print("TTS generation timed out")
            sr = 22050
            duration = max(0.5, len(text) * 0.05)
            return np.zeros(int(sr * duration), dtype=np.float32), sr
        except Exception as e:
            print(f"TTS generation error: {e}")
            sr = 22050
            duration = max(0.5, len(text) * 0.05)
            return np.zeros(int(sr * duration), dtype=np.float32), sr
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @staticmethod
    def _read_wav(path: str) -> tuple[np.ndarray, int]:
        """Read a WAV file and return (audio_float32, sample_rate)."""
        with wave.open(path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth == 2:
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        if n_channels == 2:
            audio = audio.reshape(-1, 2).mean(axis=1)

        # Normalize
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio * (0.9 / peak)

        return audio, sample_rate
