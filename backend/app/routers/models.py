from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.engines.registry import engine_registry
from app.schemas import ModelInfo, ModelListResponse

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
async def list_models():
    models = engine_registry.list_all()
    return ModelListResponse(
        models=[ModelInfo(**m) for m in models],
        active_model=engine_registry.active_name,
    )


@router.post("/{name}/download")
async def download_model(name: str):
    import asyncio as _asyncio
    import json

    if name not in engine_registry.engines:
        raise HTTPException(status_code=404, detail=f"Engine '{name}' not found")

    engine = engine_registry.engines[name]
    if engine.is_downloaded():
        return {"status": "already_downloaded"}

    async def progress_stream():
        progress_value = [0]
        download_done = _asyncio.Event()
        download_error = [None]

        def on_progress(pct: int):
            progress_value[0] = pct

        async def run_download():
            try:
                await engine.download(progress_callback=on_progress)
            except Exception as e:
                download_error[0] = str(e)
            finally:
                download_done.set()

        task = _asyncio.create_task(run_download())

        yield f"data: {json.dumps({'status': 'downloading', 'progress': 0})}\n\n"

        # Send heartbeat every 3s so the SSE connection stays alive
        while not download_done.is_set():
            try:
                await _asyncio.wait_for(download_done.wait(), timeout=3.0)
            except _asyncio.TimeoutError:
                pass
            current = progress_value[0]
            yield f"data: {json.dumps({'status': 'downloading', 'progress': current})}\n\n"

        await task  # ensure exceptions propagate

        if download_error[0]:
            yield f"data: {json.dumps({'status': 'error', 'error': download_error[0]})}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'completed', 'progress': 100})}\n\n"

    return StreamingResponse(progress_stream(), media_type="text/event-stream")


@router.post("/{name}/load")
async def load_model(name: str):
    try:
        await engine_registry.get(name)
        return {"status": "loaded", "model": name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/unload")
async def unload_model(name: str):
    if name not in engine_registry.engines:
        raise HTTPException(status_code=404, detail=f"Engine '{name}' not found")
    if engine_registry.active_name == name:
        await engine_registry.unload_active()
    return {"status": "unloaded"}


@router.delete("/{name}")
async def delete_model(name: str):
    if name not in engine_registry.engines:
        raise HTTPException(status_code=404, detail=f"Engine '{name}' not found")

    engine = engine_registry.engines[name]
    if engine.is_loaded:
        await engine_registry.unload_active()

    import shutil
    model_dir = engine.models_dir / name
    if model_dir.exists():
        shutil.rmtree(model_dir)
    return {"status": "deleted"}
