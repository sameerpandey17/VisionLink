"""
Redis Pub/Sub WebSocket broadcaster.

IDENTIFIED ISSUE — In-Memory Broadcaster Scaling Trap
------------------------------------------------------
The original ConnectionManager stored WebSocket connections in a Python list:

    class ConnectionManager:
        def __init__(self):
            self._connections: list[WebSocket] = []

This works perfectly for a single-process server. The moment you scale to
multiple Uvicorn workers (--workers 4), or run multiple replicas behind a
load balancer, it silently breaks:

  Browser A → Worker 1 (has [ws_A] in its list)
  POST /ingest → Worker 2 (has [] — empty list, nobody receives the frame)

Worker 2 broadcasts to its own empty list. Browser A, sitting on Worker 1,
never receives the frame. No error, no warning — just a frozen stream.

FIX — Redis Pub/Sub Message Bus
--------------------------------
Instead of each worker maintaining its own connection list, every worker
publishes frames to a Redis channel. Each WebSocket handler subscribes
to that channel independently.

  POST /ingest → any worker → redis.publish("face_frames", jpeg_bytes)
                                        ↓
                         Redis broadcasts to all subscribers
                                        ↓
              Worker 1 subscriber → ws_A.send_bytes(frame)
              Worker 2 subscriber → ws_B.send_bytes(frame)

Now every client on every worker sees every frame. This is the standard
pattern for horizontally scalable WebSocket broadcasts (used by Discord,
Slack, etc. at massive scale).

LIFECYCLE
---------
  broadcaster.startup()   → called in FastAPI lifespan on boot
  broadcaster.shutdown()  → called in FastAPI lifespan on shutdown
  broadcaster.publish()   → called by POST /ingest after rendering
  broadcaster.subscribe() → called by GET /stream WebSocket handler
"""

import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.config import settings

logger = logging.getLogger(__name__)

_CHANNEL = "face_frames"


class RedisBroadcaster:
    """
    Thin wrapper around a Redis Pub/Sub channel.

    One application-level instance is created at module load time and
    shared across all requests (like the original ConnectionManager).
    The difference is that publish/subscribe go through Redis, so all
    worker processes share the same message stream.
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def startup(self) -> None:
        """Open the shared Redis connection. Call once at app startup."""
        self._redis = await aioredis.from_url(
            settings.redis_url,
            decode_responses=False,  # We transmit raw JPEG bytes, not strings
            max_connections=100,    # Allow high concurrency for pub/sub subscribers
        )
        logger.info("Redis broadcaster connected → %s", settings.redis_url)

    async def shutdown(self) -> None:
        """Close the Redis connection gracefully on app shutdown."""
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis broadcaster disconnected.")

    async def publish(self, data: bytes) -> None:
        """
        Publish a rendered frame to all subscribers on all workers.

        This replaces the old manager.broadcast_bytes() call in /ingest.
        The frame travels: ingest handler → Redis → all subscriber loops.
        """
        if self._redis is None:
            logger.warning("publish() called before startup() — frame dropped.")
            return
        await self._redis.publish(_CHANNEL, data)

    async def subscribe(self, ws: WebSocket) -> None:
        """
        Subscribe to the Redis channel and relay every frame to one client.

        Called once per connected browser tab. Each subscriber gets its own
        Redis pubsub object — they are independent and don't block each other.

        Slow clients: if ws.send_bytes() raises (client gone), we break the
        loop and clean up the subscription. Other clients are unaffected.
        """
        if self._redis is None:
            logger.warning("subscribe() called before startup() — no stream.")
            return

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_CHANNEL)
        logger.info("WS client subscribed to Redis channel '%s'.", _CHANNEL)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue  # Skip subscribe/unsubscribe confirmation messages
                frame_bytes: bytes = message["data"]
                try:
                    await ws.send_bytes(frame_bytes)
                except Exception:
                    logger.info("WS send failed — client disconnected, closing subscription.")
                    break
        finally:
            await pubsub.unsubscribe(_CHANNEL)
            await pubsub.aclose()
            logger.info("WS client unsubscribed from Redis channel '%s'.", _CHANNEL)


# Application-level singleton — one broadcaster per process, all share Redis
broadcaster = RedisBroadcaster()
