import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.broadcaster import broadcaster
from app.core.detector import init_detector
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialise MediaPipe, connect to Redis broadcaster, connect to DB.
    Shutdown: close Redis broadcaster connection cleanly.
    """
    logger.info("Initialising face detector...")
    init_detector()

    # NEW: Start Redis broadcaster so publish/subscribe work at request time.
    # broadcaster.startup() opens the persistent Redis connection used by
    # all /ingest publish calls and all /stream subscribe loops.
    logger.info("Connecting Redis broadcaster...")
    await broadcaster.startup()

    logger.info("Connecting to database with retry...")
    for attempt in range(3):
        try:
            await init_db()
            logger.info("Database connection established.")
            break
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                "DB connect failed (attempt %d/3): %s — retrying in %ds",
                attempt + 1, exc, wait,
            )
            if attempt == 2:
                raise RuntimeError("Could not connect to database after 3 attempts.") from exc
            await asyncio.sleep(wait)

    yield  # ── app runs ──

    # Graceful shutdown: release Redis connection before the process exits.
    logger.info("Shutting down Redis broadcaster...")
    await broadcaster.shutdown()


app = FastAPI(title="Face Detection Stream API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all for unhandled exceptions — return clean JSON instead of HTML traceback."""
    logger.exception("Unhandled error on %s: %s", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Check server logs."},
    )


# Register routers
from app.api.ingest import router as ingest_router  # noqa: E402
from app.api.stream import router as stream_router  # noqa: E402
from app.api.roi import router as roi_router  # noqa: E402

app.include_router(ingest_router)
app.include_router(stream_router)
app.include_router(roi_router)
