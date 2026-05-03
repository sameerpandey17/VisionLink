# Real-Time Face Detection Video Streaming System — Engineering Prompt

---

## What this is

You're building a containerized, real-time video processing system. A video feed comes in one end, faces get detected and boxed, and the processed stream goes back out to a browser. Everything runs in Docker. The goal is a working system, not a showcase of complexity — keep it simple where the problem lets you.

Read this whole document before writing a single line of code. A lot of the "why" is in the sections that come after the "what".

---

## The core loop (understand this first)

```
video source → POST /ingest → detect face → draw ROI box → broadcast via WS → React frontend
                                    ↓
                             save to postgres
```

That's it. Everything else — Nginx, Docker Compose, the data endpoint — exists to support this loop cleanly. Don't lose sight of it.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async-native, good WebSocket support, typed |
| Face detection | MediaPipe | Lightweight, no GPU needed, no OpenCV dependency |
| ROI rendering | Pillow (PIL) | Draws the bounding box — OpenCV must NOT be used for this |
| Database | PostgreSQL | Relational, sessions/detections map naturally to tables |
| Frontend | React.js | Required by spec |
| Orchestration | Docker Compose | Single `docker-compose up` should start everything |
| Proxy | Nginx | Routes WebSocket upgrades and REST traffic on port 80 |

The constraint on OpenCV is real — MediaPipe can be used for detection internally (it uses OpenCV under the hood), but the actual rectangle drawing on the frame must go through Pillow's `ImageDraw`. Don't conflate detection with rendering.

---

## API surface

Three endpoints. That's all. Don't add more unless there's a documented reason.

### POST /ingest
Receives raw video frames from the source. Accepts `multipart/form-data` with a single file field (`frame`). The content type should be `image/jpeg` or `image/png`.

**What it does:**
1. Validates the uploaded file (type, size — see constraints below)
2. Runs face detection via MediaPipe
3. If a face is found — draws the ROI using Pillow, saves detection metadata to Postgres, broadcasts the rendered frame to all connected WebSocket clients
4. If no face is found — broadcasts the original frame as-is (so the stream doesn't stall), logs a miss
5. Returns `{ "detected": true/false, "box": { x, y, w, h } | null }`

**What it does NOT do:** Store the frame image itself. Only the bounding box coordinates and metadata go to the database.

### WS /stream
The egress. Clients connect here and receive a continuous stream of processed JPEG frames as binary WebSocket messages. The frontend renders these as a video by swapping an `<img>` src on each message.

The server holds a list of active connections and broadcasts to all of them on each ingest call. If a client disconnects mid-stream, handle it gracefully — remove it from the list, don't crash the broadcast loop.

### GET /api/roi
Returns raw ROI data — no image, just coordinates. Used by the frontend to draw its own canvas overlay independently from the video stream.

Query params:
- `session_id` (optional) — filter by session
- `limit` (optional, default 100, max 1000)
- `since` (optional, ISO timestamp) — returns only records after this time

Response: `{ "detections": [ { id, timestamp, session_id, x, y, width, height, confidence, frame_id } ] }`

---

## Database schema

Two tables. Nothing more.

```sql
-- One row per streaming session
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    source_label TEXT  -- optional human-readable label, e.g. "webcam-1"
);

-- One row per detected face per frame
CREATE TABLE roi_detections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    frame_id    BIGINT NOT NULL,     -- monotonic counter within the session
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    confidence  FLOAT NOT NULL,
    CHECK (x >= 0 AND y >= 0 AND width > 0 AND height > 0),
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE INDEX idx_roi_session_ts ON roi_detections (session_id, timestamp DESC);
```

Use Alembic for migrations. Don't run raw SQL in the app startup — the migration should be a tracked, versioned file.

---

## Project structure

```
face-detection-system/
│
├── docker-compose.yml
├── architecture.png              ← required by spec — include a diagram
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   │   ├── alembic.ini
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   └── app/
│       ├── main.py               ← FastAPI app entry point
│       ├── config.py             ← settings via pydantic-settings + env vars
│       │
│       ├── api/
│       │   ├── ingest.py
│       │   ├── stream.py
│       │   └── roi.py
│       │
│       ├── core/
│       │   ├── detector.py       ← MediaPipe wrapper only
│       │   ├── renderer.py       ← Pillow drawing only
│       │   └── broadcaster.py    ← WebSocket connection manager
│       │
│       └── db/
│           ├── models.py
│           ├── schemas.py
│           ├── crud.py
│           └── session.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── VideoStream.jsx   ← img tag, swaps src on WS binary message
│       │   ├── RoiCanvas.jsx     ← canvas overlay using /api/roi data
│       │   └── StatsPanel.jsx
│       └── hooks/
│           └── useWebSocket.js
│
└── nginx/
    └── nginx.conf
```

Keep `core/` clean — no database calls, no HTTP logic. It's just functions. `api/` wires them together with the web layer. `db/` handles persistence. This separation is intentional and will be evaluated.

---

## Detailed implementation notes

### detector.py

MediaPipe's face detection model runs per-frame. Initialize it once at module level (or on app startup via a FastAPI lifespan event) — do not re-initialize it on every request. That's expensive.

```python
@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    image_width: int   # needed to clamp box to frame bounds
    image_height: int

def detect_face(frame_bytes: bytes) -> BoundingBox | None:
    ...
```

Return `None` when no face is found. Don't raise an exception — a frame with no face is a normal operating condition, not an error.

Clamp the bounding box to the image dimensions before returning. MediaPipe occasionally returns boxes that bleed slightly outside the frame boundary.

### renderer.py

Takes frame bytes and a `BoundingBox`, returns JPEG bytes with a rectangle drawn on it. Pillow only.

```python
def draw_roi(frame_bytes: bytes, box: BoundingBox) -> bytes:
    img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [box.x, box.y, box.x + box.width, box.y + box.height],
        outline=(0, 255, 0),
        width=2
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
```

Don't hardcode the outline color — accept it as a parameter with a sensible default. Makes testing easier.

### broadcaster.py

Manage the list of active WebSocket connections. The key problem here is that `broadcast_bytes` will be called frequently (once per ingested frame). If a client is slow or has already disconnected, the send will fail — catch that, remove the client, don't let one bad client block others.

```python
class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None: ...
    def disconnect(self, ws: WebSocket) -> None: ...

    async def broadcast_bytes(self, data: bytes) -> None:
        dead = []
        for ws in self._connections:
            try:
                await ws.send_bytes(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
```

One shared `ConnectionManager` instance per app process. Create it at module level or via FastAPI's dependency injection.

### ingest.py — the main request handler

This is where the pieces connect. The happy path looks like:

1. Read uploaded file bytes
2. Validate (see constraints below)
3. Call `detect_face(bytes)` → `box | None`
4. If `box`: call `draw_roi(bytes, box)` → rendered bytes; else use original bytes
5. Save to DB if `box` is not None (async, don't block the response on this)
6. `await broadcaster.broadcast_bytes(rendered_or_original)`
7. Return JSON response

Step 5 being async is important. You don't want the HTTP response to wait on a database write. Use `asyncio.create_task` or run it in the background.

---

## Edge cases to handle explicitly

These aren't optional — they're what separates a toy from something real.

### Frame ingestion

**Invalid file type** — reject anything that isn't JPEG or PNG. Check the magic bytes, not just the Content-Type header. Content-Type is trivially spoofed.

```python
MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n': 'image/png',
}
```

**Oversized frames** — set a hard limit (suggest 10MB). Reject before attempting decode or detection. Return HTTP 413.

**Corrupted image data** — `Image.open()` will throw if the bytes aren't a valid image. Wrap it, return HTTP 422 with a clear message.

**No active WebSocket clients** — this is fine. Detect, save to DB, skip the broadcast. Don't error.

**MediaPipe model not loaded** — if the detector fails to initialize at startup (rare, but possible on bad installs), the app should fail fast with a clear startup error rather than silently failing on every request.

**Multiple faces in frame** — the spec says assume one face, but the real world doesn't cooperate. Pick the highest-confidence detection and use only that one. Log a warning if multiple are found.

### WebSocket stream

**Client connects before any frames arrive** — this is fine. The connection just waits. Don't send a "no data yet" message; let it sit.

**Client disconnects mid-stream** — already handled in `broadcaster.py` above. The key is not propagating the exception back up.

**Client sends data to /stream** — the stream endpoint is send-only from the server's perspective. If a client sends data, just ignore it (read and discard in a loop, or set `receive_mode` appropriately in FastAPI). Don't crash.

**Very slow client** — if a client can't keep up with the frame rate, its send queue fills up. Two options: drop frames for that client (simpler, preferred for video) or close the connection after N failed sends. Pick one and document it.

### Database

**Postgres not available on startup** — the backend should retry the connection with exponential backoff rather than crashing immediately. Three retries over 10 seconds is reasonable. After that, crash with a clear error message.

**DB write fails during active stream** — log the error, don't crash the request. A failed DB write shouldn't interrupt the video stream.

**Long-running sessions with many detections** — the `roi_detections` table will grow. The index on `(session_id, timestamp DESC)` handles query performance. Add a note in the README about archiving old sessions.

### Frontend / WebSocket client

**Connection drops** — implement reconnect with backoff in `useWebSocket.js`. Try immediately on drop, then 1s, 2s, 4s, max 30s. Show a "reconnecting…" indicator in the UI.

**Stream lags behind** — if the browser's image update can't keep up, just always display the latest received frame. Don't queue frames.

**Browser tab hidden** — when the tab goes to background, `visibilitychange` fires. Optionally pause frame rendering (not the WS connection — just stop updating the img src) to save CPU.

---

## Security

This is a local dev system per spec, but write it like it's going to production anyway. The evaluation rubric includes security.

### Input validation

- Validate file type by magic bytes, not Content-Type
- Hard limit on request body size — set at both Nginx (`client_max_body_size 10m`) and FastAPI (`UploadFile` size check)
- Reject empty filenames, path traversal characters in any string field
- All query params on `GET /api/roi` go through Pydantic validation — `limit` is clamped to [1, 1000], `since` must be a valid ISO timestamp

### Database

- Use SQLAlchemy parameterized queries everywhere. No string formatting in SQL. Ever.
- Database credentials go in a `.env` file, not hardcoded. Add `.env` to `.gitignore` from day one.
- The app connects as a user with only the permissions it needs (`SELECT`, `INSERT` on the two tables). Not as a superuser. Document how to set this up in the README.

### Headers (via Nginx)

Add these to the Nginx config:

```nginx
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options DENY;
add_header X-XSS-Protection "1; mode=block";
```

### WebSocket

- Nginx should handle the upgrade properly. Make sure `Upgrade` and `Connection` headers are forwarded.
- Don't accept binary messages from clients on the `/stream` endpoint. Read and discard, or don't read at all.

### CORS

For local dev, allow `http://localhost:3000` explicitly. Don't use `*` — it makes the setup hard to secure later.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Rate limiting

For a local dev system this is optional, but add a note in the README about where you'd put it if this went to production (Nginx `limit_req_zone` or a middleware layer).

---

## Docker Compose setup

Four services: `backend`, `frontend`, `db`, `nginx`. One network. One named volume for Postgres data.

```yaml
# rough structure — fill in the details
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: facedetect
      POSTGRES_USER: facedetect
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U facedetect"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://facedetect:${POSTGRES_PASSWORD}@db:5432/facedetect
    ports: []   # don't expose directly — let Nginx handle it

  frontend:
    build: ./frontend
    ports: []   # same

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    depends_on:
      - backend
      - frontend

volumes:
  pgdata:
```

The backend should not be reachable directly on any port. Everything goes through Nginx. This is both cleaner and more realistic.

The `backend` Dockerfile should run Alembic migrations before starting Uvicorn. Use a shell entrypoint:

```sh
#!/bin/sh
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Testing

The evaluation rubric calls out "meaningful test coverage for critical paths." These are the critical paths:

**Must have:**
- `test_detector.py` — test with a real image containing a face (include a small test fixture), test with a blank frame (no face), test with corrupted bytes
- `test_renderer.py` — test that the output is valid JPEG, test that the rectangle is within image bounds, test with a zero-size box (edge case)
- `test_api.py` — test `POST /ingest` with a valid frame, test with wrong content type, test with oversized file, test `GET /api/roi` filtering by session_id

**Use pytest + pytest-asyncio.** FastAPI's `TestClient` handles HTTP tests fine. For WebSocket testing, use `starlette.testclient.TestClient` as a context manager.

Don't aim for 100% coverage. Aim for tests that would catch a real bug — the detector returning wrong coordinates, a frame type check being skipped, a DB write failing silently.

---

## README requirements

Someone should be able to clone this repo and run it in under 5 minutes. The README needs:

1. **Prerequisites** — Docker + Docker Compose version, that's it
2. **Setup** — copy `.env.example` to `.env`, fill in one password, run `docker-compose up`
3. **How to send a frame** — a working `curl` command they can copy-paste
4. **How to view the stream** — open `http://localhost` in a browser
5. **How to query ROI data** — a working `curl` example for `GET /api/roi`
6. **Architecture** — one paragraph + the diagram image
7. **Design decisions** — three or four bullet points explaining why you made the non-obvious choices (why Nginx, why Pillow not OpenCV, why async DB writes)

Don't write a README that reads like a spec. Write it like you're handing this to a teammate on their first day.

---

## Commit history guidance

The evaluation rubric specifically mentions "meaningful commit history that tells a story." That means:

- First commit: project structure and Docker setup (nothing works yet, that's fine)
- Then: database schema + migrations
- Then: `core/` — detector and renderer (with tests)
- Then: the three API endpoints
- Then: broadcaster + WebSocket stream
- Then: React frontend
- Then: Nginx config wiring it together
- Then: README

Each commit message should say what changed and why, not just "update files" or "fix bug." Example: `add frame size validation — reject > 10MB before hitting detector` is a good commit message. `fix stuff` is not.

---

## What not to build

These are things the spec doesn't ask for. Don't add them. They'll be counted against you under "pragmatism."

- Authentication or user accounts
- Frame storage / video archiving
- Multiple face detection (handle gracefully, but don't build a multi-face feature)
- A WebRTC pipeline (WebSockets are explicitly required)
- Admin dashboards
- Any ML model training or fine-tuning

If you want to add something that isn't in this spec, write a comment in the code explaining why. Don't just add it.

---

## Quick reference — response codes

| Situation | HTTP code |
|---|---|
| Successful ingest, face detected | 200 |
| Successful ingest, no face found | 200 (not 204 — still a valid response) |
| Wrong file type | 415 Unsupported Media Type |
| File too large | 413 Request Entity Too Large |
| Corrupted image data | 422 Unprocessable Entity |
| Missing required field | 422 |
| Database unavailable | 503 Service Unavailable |
| Unexpected server error | 500 (with a generic message — don't leak stack traces) |

---

## Final note

The point of this system is the processing loop — frame in, face detected, box drawn, frame out, coordinates saved. Everything else is scaffolding. When you're not sure whether to add something, ask whether it makes that loop more reliable, more observable, or more correct. If the answer is no, skip it.
