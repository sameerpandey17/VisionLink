#  VisionLink: Face Detection Stream v2.0

A production-grade, real-time video processing system. Ingest video frames, detect faces with MediaPipe, render annotations with Pillow, and broadcast to unlimited clients via Redis Pub/Sub.

---

##  Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- **BuildKit enabled** (for fast builds): `export DOCKER_BUILDKIT=1`

### 2. Setup & Run
```bash
# Clone and enter
cd "VisionLink"

# Initialize environment
cp .env.example .env
# Optional: Edit .env to set an API_KEY for security

# Launch the stack
docker-compose up --build
```
- **Dashboard:** [http://localhost](http://localhost)
- **API Docs:** [http://localhost/docs](http://localhost/docs) (Swagger)

---

##  Architecture & Data Flow

VisionLink is built for horizontal scalability. Unlike basic implementations that store connections in memory, this system uses a distributed message bus.

### The Life of a Frame:
1.  **Ingest:** A source (camera/script) POSTs a JPEG to `/ingest`.
2.  **Process:** Backend validates the `X-API-Key`, runs MediaPipe detection, and draws the ROI box using Pillow.
3.  **Persist:** Metadata is sent to a background task. It fetches an atomic ID from a **Postgres Sequence** and saves the record.
4.  **Broadcast:** The rendered JPEG is published to a **Redis channel**.
5.  **Egress:** All connected WebSocket clients (`/stream`) receive the frame from Redis and update their `<img>` tags in React.

---

##  File Structure & Responsibilities

### 🔹 Backend (`/backend`)
| File | Responsibility |
| :--- | :--- |
| `app/main.py` | Entry point. Handles lifespan (Redis/DB init) and global error handling. |
| `app/api/ingest.py` | Receives frames. Handles validation, detection triggering, and background saves. |
| `app/api/stream.py` | WebSocket endpoint. Subscribes clients to the Redis frame stream. |
| `app/api/roi.py` | Query API for detection history. Features **Cursor-based pagination**. |
| `app/api/deps.py` | Security layer. Implements API Key validation. |
| `app/core/detector.py` | MediaPipe wrapper. Pure detection logic (no rendering). |
| `app/core/renderer.py` | Pillow drawing logic. Crops, draws boxes, and encodes to JPEG. |
| `app/core/broadcaster.py` | The "Message Bus". Uses Redis Pub/Sub to share frames across workers. |
| `app/db/crud.py` | Database operations. Uses SQL sequences and keyset pagination. |
| `app/db/models.py` | SQLAlchemy models for Sessions and ROI Detections. |
| `Dockerfile` | Optimized build using **BuildKit cache mounts** for 10x faster builds. |

### 🔹 Frontend (`/frontend`)
| File | Responsibility |
| :--- | :--- |
| `src/App.tsx` | Main dashboard. Manages WebSocket lifecycle and UI state. |
| `src/components/` | Reusable UI: `StreamView`, `DetectionLog`, `StatsCard`. |
| `Dockerfile` | Nginx-based production build with multi-stage caching. |

### 🔹 Infrastructure
| File | Responsibility |
| :--- | :--- |
| `docker-compose.yml` | Orchestrates Backend, Frontend, Postgres, Redis, and Nginx. |
| `nginx/nginx.conf` | Reverse proxy. Handles WebSocket upgrades and routing. |
| `.dockerignore` | Crucial for build speed; prevents large local folders from slowing down Docker. |

---

##  Security & Reliability (v2)

We improved the system's baseline from a "demo" to "production-ready":

-   **API Key Auth:** The `/ingest` endpoint is protected by an `X-API-Key` header to prevent unauthorized resource exhaustion.
-   **No Silent Failures:** DB writes use background tasks with `add_done_callback` to ensure any persistence errors are logged without dropping the video stream.
-   **Horizontal Scaling:** By using Redis instead of in-memory lists, you can run 10+ backend workers and every client will still see every frame.
-   **Crash-Safe Counting:** Frame IDs come from a Database Sequence, ensuring IDs never reset or collide after a server restart.

---

## API Reference

### `POST /ingest`
Sends a frame for processing.
- **Header:** `X-API-Key: <your_key>` (if enabled)
- **Body:** `multipart/form-data` with `frame` field.

### `GET /api/roi`
Retrieves detection history.
- **Params:** `limit`, `session_id`, `since`, `after` (cursor).
- **Pagination:** Uses `next_cursor` from the response to fetch the next page via `?after=...`.

---

##  Testing

The system includes comprehensive integration tests covering auth, processing, and pagination.

```bash
# Run all tests in a clean container
docker-compose run --rm backend pytest
```

---

## Technical Choices
- **FastAPI:** High-performance async Python framework.
- **MediaPipe:** Google's state-of-the-art ML for face detection.
- **Pillow:** Robust image manipulation without the heavy overhead of OpenCV.
- **Redis Pub/Sub:** Industry standard for scalable real-time messaging.
- **PostgreSQL:** Reliable relational storage with strong data integrity.
