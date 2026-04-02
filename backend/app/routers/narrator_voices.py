"""Narrator voice management — import from folder, auto-process, and manage."""
import asyncio
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_session
from app.db.models import Voice

router = APIRouter(prefix="/api/narrator-voices", tags=["narrator-voices"])

IMPORT_DIR = settings.data_dir / "voices" / "import"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/import-folder")
async def get_import_folder():
    """Return the import folder path and list files in it."""
    files = []
    for f in IMPORT_DIR.iterdir():
        if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a"):
            files.append({
                "name": f.name,
                "size_kb": f.stat().st_size // 1024,
                "extension": f.suffix.lower(),
            })
    return {
        "path": str(IMPORT_DIR),
        "files": sorted(files, key=lambda x: x["name"]),
        "count": len(files),
    }


@router.post("/import-all")
async def import_all_voices():
    """Copy all audio files from the import folder to staging for review.
    Files are copied as-is (no conversion) for speed. Conversion happens at add time."""
    import asyncio

    STAGING_DIR = settings.base_dir / "data" / "voices" / "staging"
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    files = [f for f in IMPORT_DIR.iterdir()
             if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".opus")]
    if not files:
        return {"status": "empty", "imported": 0, "failed": 0,
                "message": f"No audio files found in {IMPORT_DIR}"}

    imported = []
    failed = []

    def _copy_all():
        for f in sorted(files):
            try:
                stage_id = str(uuid.uuid4())
                ext = f.suffix.lower().lstrip(".")
                dest = STAGING_DIR / f"{stage_id}.{ext}"
                shutil.copy2(str(f), str(dest))

                # Quick duration probe via ffprobe (fast, no decode)
                duration = None
                try:
                    import subprocess
                    result = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries",
                         "format=duration", "-of", "csv=p=0", str(dest)],
                        capture_output=True, text=True, timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        duration = round(float(result.stdout.strip()), 2)
                except Exception:
                    pass

                imported.append({
                    "stage_id": stage_id,
                    "filename": f.name,
                    "duration": duration,
                    "size": dest.stat().st_size,
                    "audio_url": f"/audio/voices/staging/{dest.name}",
                })
            except Exception as e:
                failed.append({"name": f.name, "error": str(e)})

    await asyncio.get_event_loop().run_in_executor(None, _copy_all)

    return {
        "status": "done",
        "imported": len(imported),
        "failed": len(failed),
        "staged": imported,
        "errors": failed,
    }

