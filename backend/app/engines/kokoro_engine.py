import asyncio
import os
from pathlib import Path
from typing import Optional

import numpy as np

from app.engines.base import TTSEngine

# Fix espeak-ng data path for Kokoro's phonemizer
try:
    import espeakng_loader
    _espeak_dir = str(Path(espeakng_loader.__file__).parent)
    os.environ.setdefault('PHONEMIZER_ESPEAK_LIBRARY', str(Path(_espeak_dir) / 'espeak-ng.dll'))
    os.environ.setdefault('PHONEMIZER_ESPEAK_DATA', str(Path(_espeak_dir) / 'espeak-ng-data'))
    os.environ.setdefault('ESPEAK_DATA_PATH', str(Path(_espeak_dir) / 'espeak-ng-data'))
except ImportError:
    pass

# Complete Kokoro voice catalog — all 54 voices across 9 languages
KOKORO_VOICES = {
    # American English (lang_code='a')
    "en_female": [
        "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    ],
    "en_male": [
        "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
        "am_michael", "am_onyx", "am_puck", "am_santa",
    ],
    # British English (lang_code='b')
    "en_gb_female": ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"],
    "en_gb_male": ["bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
    # Japanese (lang_code='j')
    "ja_female": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro"],
    "ja_male": ["jm_kumo"],
    # Mandarin Chinese (lang_code='z')
    "zh_female": ["zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi"],
    "zh_male": ["zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"],
    # Spanish (lang_code='e')
    "es_female": ["ef_dora"],
    "es_male": ["em_alex", "em_santa"],
    # French (lang_code='f')
    "fr_female": ["ff_siwis"],
    # Hindi (lang_code='h')
    "hi_female": ["hf_alpha", "hf_beta"],
    "hi_male": ["hm_omega", "hm_psi"],
    # Italian (lang_code='i')
    "it_female": ["if_sara"],
    "it_male": ["im_nicola"],
    # Brazilian Portuguese (lang_code='p')
    "pt_female": ["pf_dora"],
    "pt_male": ["pm_alex", "pm_santa"],
}

# Flat list for quick lookup
ALL_VOICES = []
for voices_list in KOKORO_VOICES.values():
    ALL_VOICES.extend(voices_list)

# Human-readable display names
VOICE_DISPLAY_NAMES = {
    # American English Female
    "af_heart": "Heart (US Female, Flagship)",
    "af_alloy": "Alloy (US Female)",
    "af_aoede": "Aoede (US Female)",
    "af_bella": "Bella (US Female)",
    "af_jessica": "Jessica (US Female)",
    "af_kore": "Kore (US Female)",
    "af_nicole": "Nicole (US Female)",
    "af_nova": "Nova (US Female)",
    "af_river": "River (US Female)",
    "af_sarah": "Sarah (US Female)",
    "af_sky": "Sky (US Female)",
    # American English Male
    "am_adam": "Adam (US Male)",
    "am_echo": "Echo (US Male)",
    "am_eric": "Eric (US Male)",
    "am_fenrir": "Fenrir (US Male)",
    "am_liam": "Liam (US Male)",
    "am_michael": "Michael (US Male)",
    "am_onyx": "Onyx (US Male)",
    "am_puck": "Puck (US Male)",
    "am_santa": "Santa (US Male)",
    # British English Female
    "bf_alice": "Alice (UK Female)",
    "bf_emma": "Emma (UK Female)",
    "bf_isabella": "Isabella (UK Female)",
    "bf_lily": "Lily (UK Female)",
    # British English Male
    "bm_daniel": "Daniel (UK Male)",
    "bm_fable": "Fable (UK Male)",
    "bm_george": "George (UK Male)",
    "bm_lewis": "Lewis (UK Male)",
    # Japanese Female
    "jf_alpha": "Alpha (JA Female)",
    "jf_gongitsune": "Gongitsune (JA Female)",
    "jf_nezumi": "Nezumi (JA Female)",
    "jf_tebukuro": "Tebukuro (JA Female)",
    # Japanese Male
    "jm_kumo": "Kumo (JA Male)",
    # Chinese Female
    "zf_xiaobei": "Xiaobei (ZH Female)",
    "zf_xiaoni": "Xiaoni (ZH Female)",
    "zf_xiaoxiao": "Xiaoxiao (ZH Female)",
    "zf_xiaoyi": "Xiaoyi (ZH Female)",
    # Chinese Male
    "zm_yunjian": "Yunjian (ZH Male)",
    "zm_yunxi": "Yunxi (ZH Male)",
    "zm_yunxia": "Yunxia (ZH Male)",
    "zm_yunyang": "Yunyang (ZH Male)",
    # Spanish
    "ef_dora": "Dora (ES Female)",
    "em_alex": "Alex (ES Male)",
    "em_santa": "Santa (ES Male)",
    # French
    "ff_siwis": "Siwis (FR Female)",
    # Hindi
    "hf_alpha": "Alpha (HI Female)",
    "hf_beta": "Beta (HI Female)",
    "hm_omega": "Omega (HI Male)",
    "hm_psi": "Psi (HI Male)",
    # Italian
    "if_sara": "Sara (IT Female)",
    "im_nicola": "Nicola (IT Male)",
    # Portuguese
    "pf_dora": "Dora (PT Female)",
    "pm_alex": "Alex (PT Male)",
    "pm_santa": "Santa (PT Male)",
}

DEFAULT_VOICE = "af_heart"


class KokoroEngine(TTSEngine):
    name = "kokoro"
    display_name = "Kokoro"
    supported_languages = ["en", "en-gb", "ja", "zh", "ko", "fr", "es", "de", "it", "pt", "hi"]
    requires_gpu = False
    vram_required_mb = 500
    model_size_mb = 200
    license = "Apache-2.0"
    description = "Top-quality TTS, 82M params. Near ElevenLabs quality, blazing fast. 54 voices across 9 languages."

    def __init__(self, models_dir: Path, device: str = "cuda"):
        super().__init__(models_dir, device)
        self._model_dir = models_dir / "kokoro"
        self._pipeline = None
        self._pipelines = {}  # Cache pipelines by lang_code

    def is_downloaded(self) -> bool:
        try:
            import kokoro  # noqa: F401
            return True
        except ImportError:
            return False

    async def download(self, progress_callback=None):
        import subprocess
        import sys

        def _install():
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "kokoro", "kokoro-voices[all]"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        await asyncio.get_event_loop().run_in_executor(None, _install)

    async def load(self) -> None:
        if self._model is not None:
            return

        def _load():
            from kokoro import KPipeline
            pipeline = KPipeline(lang_code="a")  # 'a' = American English default
            return pipeline

        self._pipeline = await asyncio.get_event_loop().run_in_executor(None, _load)
        self._model = self._pipeline  # satisfy is_loaded check

    async def unload(self) -> None:
        self._pipeline = None
        self._pipelines = {}
        self._model = None

    def get_voices(self) -> list[dict]:
        """Return all available Kokoro voices with metadata."""
        voices = []
        for code in ALL_VOICES:
            display_name = VOICE_DISPLAY_NAMES.get(code, code)
            # Determine language from voice code prefix
            prefix = code[0]
            lang_map = {
                "a": "en", "b": "en-gb", "j": "ja", "z": "zh",
                "e": "es", "f": "fr", "h": "hi", "i": "it", "p": "pt",
            }
            lang = lang_map.get(prefix, "en")
            gender = "female" if code[1] == "f" else "male"
            voices.append({
                "code": code,
                "name": display_name,
                "language": lang,
                "gender": gender,
            })
        return voices

    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        """Analyze audio and find the closest Kokoro built-in voice."""

        def _encode():
            import soundfile as sf

            audio, sr = sf.read(audio_path)
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Simple pitch analysis to determine voice gender
            rms = np.sqrt(np.mean(audio ** 2))

            # Use zero-crossing rate as a rough pitch proxy
            zero_crossings = np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))

            # Higher zero-crossing rate correlates with higher pitch (female)
            if zero_crossings > 0.05:
                voice_code = "af_heart"  # Best female voice
            else:
                voice_code = "am_adam"  # Best male voice

            # Encode voice code as bytes into a numpy array for storage compatibility
            code_bytes = voice_code.encode("utf-8")
            embedding = np.zeros(256, dtype=np.float32)
            for i, b in enumerate(code_bytes[:256]):
                embedding[i] = float(b)

            return embedding

        return await asyncio.get_event_loop().run_in_executor(None, _encode)

    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        def _generate():
            import torch as _torch
            from pathlib import Path as _Path

            # Determine voice: blended tensor, voice code, or default
            voice_code = DEFAULT_VOICE
            voice_tensor = None  # If set, use tensor directly instead of code

            # Check for blended voice (.pt file in embedding_path)
            embedding_path = kwargs.get("embedding_path", "")
            if embedding_path and str(embedding_path).endswith(".pt") and _Path(str(embedding_path)).exists():
                voice_tensor = _torch.load(str(embedding_path), weights_only=True)

            # Check if a kokoro_voice was explicitly passed
            kokoro_voice = kwargs.get("kokoro_voice")
            if kokoro_voice and kokoro_voice in ALL_VOICES:
                voice_code = kokoro_voice
            elif voice_tensor is None and voice_embedding is not None:
                try:
                    code_bytes = bytes(int(b) for b in voice_embedding[:50] if b > 0)
                    decoded = code_bytes.decode("utf-8").strip()
                    if decoded and len(decoded) > 2:
                        voice_code = decoded
                except Exception:
                    pass

            # Map language to Kokoro lang_code
            lang_map = {
                "en": "a", "en-gb": "b", "ja": "j", "zh": "z", "ko": "k",
                "fr": "f", "es": "e", "de": "d", "it": "i",
                "pt": "p", "hi": "h",
            }
            lang_code = lang_map.get(language, "a")

            # Auto-select language from voice code prefix if not using tensor
            if voice_tensor is None:
                voice_prefix = voice_code[0] if voice_code else "a"
                prefix_to_lang = {
                    "a": "a", "b": "b", "j": "j", "z": "z",
                    "e": "e", "f": "f", "h": "h", "i": "i", "p": "p",
                }
                if voice_prefix in prefix_to_lang:
                    lang_code = prefix_to_lang[voice_prefix]

            # Cache pipelines per language for speed
            from kokoro import KPipeline
            if lang_code not in self._pipelines:
                self._pipelines[lang_code] = KPipeline(lang_code=lang_code)
            pipeline = self._pipelines[lang_code]

            # Use blended tensor or voice code
            voice_param = voice_tensor if voice_tensor is not None else voice_code

            # Generate audio - KPipeline yields chunks for long text
            audio_chunks = []
            for _gs, _ps, audio_chunk in pipeline(text, voice=voice_param, speed=speed):
                if audio_chunk is not None:
                    audio_chunks.append(audio_chunk.numpy())

            if not audio_chunks:
                # Fallback: return silence
                sr = 24000
                return np.zeros(sr, dtype=np.float32), sr

            audio = np.concatenate(audio_chunks)
            sr = 24000

            # Normalize
            peak = np.abs(audio).max()
            if peak > 0:
                audio = audio / peak * 0.9

            return audio.astype(np.float32), sr

        return await asyncio.get_event_loop().run_in_executor(None, _generate)
