"""System status API — VRAM, CPU, diagnostics."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Query

from app.config import settings

router = APIRouter(prefix="/api/system", tags=["system"])

_start_time = time.time()


@router.get("/status")
async def system_status():
    """Full system status: VRAM, CPU, RAM, active model, uptime."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()

    vram_info = _get_vram()

    active_model = None
    try:
        from app.engines.registry import engine_registry
        active_model = engine_registry.active_name
    except Exception:
        pass

    return {
        "vram_used_gb": vram_info.get("used_gb", 0),
        "vram_total_gb": vram_info.get("total_gb", 0),
        "cpu_percent": round(cpu_percent, 1),
        "ram_used_gb": round(ram.used / 1e9, 1),
        "ram_total_gb": round(ram.total / 1e9, 1),
        "active_model": active_model,
        "backend_version": settings.version,
        "uptime_sec": round(time.time() - _start_time),
    }


@router.get("/vram")
async def vram_status():
    """Detailed GPU VRAM info."""
    return _get_vram()


@router.get("/diagnostics")
async def diagnostics():
    """Full system diagnostics for troubleshooting."""
    checks = {}

    # Python
    checks["python_version"] = sys.version.split()[0]

    # FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        checks["ffmpeg_installed"] = result.returncode == 0
    except Exception:
        checks["ffmpeg_installed"] = False

    # CUDA
    try:
        import torch
        checks["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            checks["gpu_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        checks["cuda_available"] = False

    # Models
    try:
        from app.engines.registry import engine_registry
        checks["models"] = [
            {
                "name": e.display_name,
                "loaded": e.is_loaded,
                "downloaded": e.is_downloaded(),
                "vram_mb": e.vram_required_mb,
            }
            for e in engine_registry.engines.values()
        ]
    except Exception:
        checks["models"] = []

    # Paths
    checks["paths"] = []
    for name, path in [
        ("data", settings.data_dir),
        ("temp", settings.temp_dir),
        ("exports", settings.exports_dir),
        ("models", settings.models_dir),
    ]:
        p = Path(path)
        checks["paths"].append({
            "name": name,
            "path": str(p),
            "exists": p.exists(),
            "writable": p.exists() and p.is_dir(),
        })

    # Disk
    try:
        disk = shutil.disk_usage(str(settings.data_dir))
        checks["disk_free_gb"] = round(disk.free / 1e9, 1)
    except Exception:
        checks["disk_free_gb"] = 0

    return checks


@router.get("/validate-path")
async def validate_path(path: str = Query(...)):
    """Check if a filesystem path exists and is writable."""
    p = Path(path)
    return {
        "path": path,
        "exists": p.exists(),
        "writable": p.exists() and (p.is_dir() or p.parent.exists()),
    }


def _get_vram() -> dict:
    """Get GPU VRAM stats."""
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total = getattr(props, 'total_memory', getattr(props, 'total_mem', 0))
            allocated = torch.cuda.memory_allocated(0)
            reserved = torch.cuda.memory_reserved(0)
            return {
                "used_gb": round(allocated / 1e9, 2),
                "reserved_gb": round(reserved / 1e9, 2),
                "total_gb": round(total / 1e9, 2),
                "percent": round(allocated / total * 100, 1) if total > 0 else 0,
                "gpu_name": props.name,
            }
    except Exception:
        pass
    return {"used_gb": 0, "total_gb": 0, "percent": 0, "gpu_name": "N/A"}
