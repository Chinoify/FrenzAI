from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np


class TTSEngine(ABC):
    name: str
    display_name: str
    supported_languages: list[str]
    requires_gpu: bool
    vram_required_mb: int
    model_size_mb: int
    license: str
    description: str

    def __init__(self, models_dir: Path, device: str = "cuda"):
        self.models_dir = models_dir
        self.device = device
        self._model = None

    @abstractmethod
    async def load(self) -> None:
        """Load model weights into memory/GPU."""
        ...

    @abstractmethod
    async def unload(self) -> None:
        """Unload model from memory/GPU."""
        ...

    @abstractmethod
    async def encode_voice(self, audio_path: str, **kwargs) -> np.ndarray:
        """Create a speaker embedding from a voice sample."""
        ...

    @abstractmethod
    async def generate(
        self,
        text: str,
        voice_embedding: Optional[np.ndarray] = None,
        language: str = "en",
        speed: float = 1.0,
        **kwargs,
    ) -> tuple[np.ndarray, int]:
        """Generate speech. Returns (audio_array, sample_rate)."""
        ...

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @abstractmethod
    def is_downloaded(self) -> bool:
        """Check if model weights exist on disk."""
        ...

    @abstractmethod
    async def download(self, progress_callback=None) -> None:
        """Download model weights from HuggingFace Hub."""
        ...
