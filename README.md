# Face Detection Stream

A containerised, real-time video processing system. Send JPEG/PNG frames in, get faces detected and boxed, and watch the annotated stream live in your browser.

```
docker-compose up --build
open http://localhost
```

---

## Prerequisites

- Docker >= 24
- Docker Compose >= 2.20

That's it.

---

## Setup

```bash
# 1. Copy the env template and set one password
cp .env.example .env
# Edit .env — change POSTGRES_PASSWORD to anything

# 2. Start everything
docker-compose up --build
```

The first run will pull base images and build. Subsequent starts are fast.

---

## Sending a frame

```bash
curl -X POST http://localhost/ingest \
  -F "frame=@/path/to/your/image.jpg" | jq
```

Response (face found):
```json
{ "detected": true, "box": { "x": 120, "y": 45, "w": 180, "h": 210 } }
```

Response (no face):
```json
{ "detected": false, "box": null }
```

---

## Watching the stream

Open `http://localhost` in a browser. The React frontend connects automatically via WebSocket and displays the annotated video stream in real-time.

---

## Querying ROI data

```bash
# Last 10 detections
curl "http://localhost/api/roi?limit=10" | jq

# Filter by session ID
curl "http://localhost/api/roi?session_id=<uuid>&limit=50" | jq

# Only detections since a timestamp
curl "http://localhost/api/roi?since=2024-01-01T00:00:00Z" | jq
```

---

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │              Docker Network              │
                        │                                         │
  Browser  ─────────▶  │  Nginx :80                              │
  curl               │  │    ├── /ingest    ──▶  Backend :8000   │
                        │    ├── /api/roi   ──▶  Backend :8000   │
                        │    ├── /stream ws ──▶  Backend :8000   │
                        │    └── /          ──▶  Frontend :80    │
                        │                         │               │
                        │                    PostgreSQL :5432     │
                        └─────────────────────────────────────────┘

Core loop:
  video source → POST /ingest → MediaPipe detect → Pillow draw ROI
      → broadcast via WebSocket → React <img> src-swap
      → save metadata to PostgreSQL (async, non-blocking)
```

See `architecture.png` for a visual diagram.

---

## Design decisions

- **Why Nginx?** The backend never needs to be publicly exposed. Nginx handles WebSocket upgrade headers, request-size limits (`client_max_body_size 10m`), and security headers in one place.

- **Why Pillow instead of OpenCV for drawing?** The spec requires it, but it's also the right call: Pillow is a lighter dependency for pure image I/O. MediaPipe uses OpenCV internally for detection, but that's invisible to the rest of the stack.

- **Why async DB writes?** The HTTP response to `/ingest` doesn't need to wait for a Postgres write to complete. Using `asyncio.create_task` means the broadcast happens immediately, and the DB write follows without blocking the caller.

- **Why WebSocket + img src-swap instead of WebRTC?** WebRTC is powerful but adds significant complexity (STUN/TURN, SDP negotiation, browser compatibility). For a controlled local system, WebSocket binary messages into an `<img>` tag is simpler, reliable, and sufficient.

---

## Database notes

Detection records accumulate over time. For production use, consider:

```sql
-- Archive sessions older than 30 days
DELETE FROM sessions WHERE started_at < now() - interval '30 days';
-- Cascades to roi_detections via ON DELETE CASCADE
```

---

## DB user setup (production)

The app only needs INSERT and SELECT. To follow least-privilege:

```sql
CREATE USER facedetect_app WITH PASSWORD 'yourpassword';
GRANT SELECT, INSERT ON sessions, roi_detections TO facedetect_app;
```

---

## Rate limiting (production note)

Not implemented for local dev. To add it, configure Nginx's `limit_req_zone` on `/ingest`, or add a middleware layer (e.g. `slowapi`) to the FastAPI app.

---

## Running tests

```bash
docker-compose run --rm backend pytest
```
