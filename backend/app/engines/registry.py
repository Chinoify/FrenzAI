from typing import Optional

from app.engines.base import TTSEngine


class EngineRegistry:
    """Manages TTS engines. Only one model loaded in GPU at a time."""

    def __init__(self):
        self._engines: dict[str, TTSEngine] = {}
        self._active: Optional[str] = None

    def register(self, engine: TTSEngine):
        self._engines[engine.name] = engine

    @property
    def active_name(self) -> Optional[str]:
        return self._active

    @property
    def engines(self) -> dict[str, TTSEngine]:
        return self._engines

    async def get(self, name: str) -> TTSEngine:
        if name not in self._engines:
            raise ValueError(f"Engine '{name}' not registered.")
        engine = self._engines[name]
        if not engine.is_downloaded():
            raise ValueError(f"Model '{name}' not downloaded yet. Go to Models page.")
        if not engine.is_loaded:
            if self._active and self._active != name:
                await self.unload_active()
            await engine.load()
            self._active = name
        return engine

    async def unload_active(self):
        if self._active and self._active in self._engines:
            engine = self._engines[self._active]
            if engine.is_loaded:
                await engine.unload()
                # Aggressive VRAM cleanup for 4GB GPU
                try:
                    import gc
                    gc.collect()
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        allocated = torch.cuda.memory_allocated(0) / (1024 * 1024)
                        print(f"[VRAM] After unloading {self._active}: {allocated:.0f}MB allocated")
                except ImportError:
                    pass
            self._active = None

    def list_all(self) -> list[dict]:
        result = []
        for engine in self._engines.values():
            result.append({
                "name": engine.name,
                "display_name": engine.display_name,
                "description": engine.description,
                "languages": engine.supported_languages,
                "vram_required_mb": engine.vram_required_mb,
                "model_size_mb": engine.model_size_mb,
                "license": engine.license,
                "is_downloaded": engine.is_downloaded(),
                "is_loaded": engine.is_loaded,
            })
        return result


# Global singleton
engine_registry = EngineRegistry()
