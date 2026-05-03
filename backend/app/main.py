import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.detector import init_detector
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init MediaPipe and DB connection pool."""
    logger.info("Initialising face detector...")
    init_detector()

    logger.info("Connecting to database with retry...")
    for attempt in range(3):
        try:
            await init_db()
            logger.info("Database connection established.")
            break
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("DB connect failed (attempt %d/3): %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt == 2:
                raise RuntimeError("Could not connect to database after 3 attempts.") from exc
            await asyncio.sleep(wait)

    yield  # ── app runs ──

    # Teardown happens here if needed


app = FastAPI(title="Face Detection Stream API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Register routers
from app.api.ingest import router as ingest_router  # noqa: E402
from app.api.stream import router as stream_router  # noqa: E402
from app.api.roi import router as roi_router  # noqa: E402

app.include_router(ingest_router)
app.include_router(stream_router)
app.include_router(roi_router)
