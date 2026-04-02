from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.db.models import Voice
from app.schemas import GPUInfo, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


def get_gpu_info() -> GPUInfo:
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            # PyTorch 2.x uses total_memory, older versions use total_mem
            vram_total = getattr(props, 'total_memory', getattr(props, 'total_mem', 0)) // (1024 * 1024)
            vram_used = torch.cuda.memory_allocated(0) // (1024 * 1024)
            return GPUInfo(
                available=True,
                name=props.name,
                vram_total_mb=vram_total,
                vram_used_mb=vram_used,
                vram_free_mb=vram_total - vram_used,
            )
    except (ImportError, Exception):
        pass
    return GPUInfo(available=False)


def get_device() -> str:
    if settings.device == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    return settings.device


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)):
    voices_count = 0
    try:
        result = await session.execute(select(func.count(Voice.id)))
        voices_count = result.scalar() or 0
    except Exception:
        pass

    # Get active model from registry if available
    active_model = None
    try:
        from app.engines.registry import engine_registry
        active_model = engine_registry.active_name
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        version=settings.version,
        gpu=get_gpu_info(),
        active_model=active_model,
        voices_count=voices_count,
        device=get_device(),
    )
