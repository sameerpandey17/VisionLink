"""
FastAPI shared dependencies — security layer.

WHY THIS FILE EXISTS
--------------------
Keeping auth logic in one module means:
  - Every endpoint that needs protection imports one line.
  - Swapping from API-Key to OAuth/JWT only changes this file.
  - Easy to write targeted unit tests for the auth logic alone.

IDENTIFIED ISSUE
----------------
The original /ingest endpoint had zero authentication. Anyone with the
server URL could POST arbitrary images, causing:
  1. Disk fill: every frame with a face writes a DB row.
  2. CPU saturation: MediaPipe runs on every incoming frame.
  3. Memory exhaustion: large image uploads close to the 10MB limit.

FIX
---
A FastAPI Dependency (require_api_key) is injected into the /ingest
endpoint's signature. FastAPI evaluates it before the handler runs, so
unauthenticated requests are rejected at the routing layer — the handler
body never executes.

  - Header: X-API-Key
  - Config: API_KEY env var (empty = auth disabled, safe for local dev)
  - Failure: 401 Unauthorized
"""

import logging

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate the X-API-Key header when authentication is enabled.

    Injects cleanly as a FastAPI dependency:
        @router.post("/ingest", dependencies=[Depends(require_api_key)])
    """
    if not settings.auth_enabled:
        return  # Dev/local mode — API_KEY not set, skip auth

    if x_api_key != settings.api_key:
        logger.warning(
            "Unauthorized /ingest attempt — bad or missing X-API-Key header."
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header.",
        )
