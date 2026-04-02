from fastapi import APIRouter, WebSocket

router = APIRouter(prefix="/api/rvc", tags=["rvc"])


@router.websocket("/stream")
async def rvc_stream(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"status": "connected", "message": "RVC streaming not yet implemented"})
    await ws.close()


@router.post("/train")
async def train_rvc():
    return {"status": "not_implemented", "message": "RVC training coming in Phase 8"}
