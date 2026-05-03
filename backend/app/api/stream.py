import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.broadcaster import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    """
    WebSocket egress endpoint.

    Clients connect here and receive a continuous stream of JPEG frames as
    binary WebSocket messages. The server broadcasts on every ingest call.

    - Client connects before any frames: fine, just waits.
    - Client sends data: read and discard (this endpoint is server → client only).
    - Client disconnects mid-stream: handled gracefully in ConnectionManager.
    - Slow clients: frames are dropped (send fails → client removed).
    """
    await manager.connect(ws)
    try:
        while True:
            # Discard any data the client sends — this is a server-push endpoint
            _ = await ws.receive_bytes()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected cleanly.")
    except Exception:
        logger.info("WebSocket client connection lost.")
    finally:
        manager.disconnect(ws)
