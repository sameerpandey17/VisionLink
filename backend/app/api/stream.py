import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.broadcaster import broadcaster

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/stream")
async def stream(ws: WebSocket) -> None:
    """WebSocket egress endpoint — server pushes JPEG frames to the browser."""
    await ws.accept()
    try:
        await broadcaster.subscribe(ws)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected cleanly.")
    except Exception as exc:
        logger.info("WebSocket connection lost: %s", exc)
