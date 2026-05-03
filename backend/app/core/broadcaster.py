import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages all active WebSocket connections and broadcasts frames to them.

    One shared instance per process — create at module level or via DI.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WS client connected. Active connections: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("WS client removed. Active connections: %d", len(self._connections))

    async def broadcast_bytes(self, data: bytes) -> None:
        """
        Send binary data to all connected clients.

        Clients that fail mid-send are collected and removed after the loop so
        that one dead client never blocks the rest.
        """
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_bytes(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Singleton — shared across all requests in this process
manager = ConnectionManager()
