import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.broadcaster import broadcaster

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    """
    WebSocket egress endpoint — server pushes JPEG frames to the browser.

    CHANGE FROM v1
    --------------
    Previously this endpoint maintained a local connection list:

        await manager.connect(ws)  # adds ws to in-memory list
        while True:
            _ = await ws.receive_bytes()  # discard client data

    The broadcast came from the ingest handler calling manager.broadcast_bytes(),
    which looped over the local list. This broke with multiple workers.

    NOW (v2)
    --------
    broadcaster.subscribe(ws) opens a Redis pub/sub subscription and
    relays messages directly to this client. The loop lives here, in this
    connection handler — no separate broadcast call needed.

    The client still doesn't need to send anything. If the client sends
    data, the Redis subscribe loop simply ignores it (the loop only reads
    from Redis, not from the WebSocket receive side).

    Disconnection: broadcaster.subscribe() catches WebSocket send failures
    and breaks the loop, cleaning up the Redis subscription automatically.
    """
    await ws.accept()
    try:
        await broadcaster.subscribe(ws)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected cleanly.")
    except Exception as exc:
        logger.info("WebSocket connection lost: %s", exc)
