# VisionLink: Emotion Detection Dashboard v2.0

A production-grade, real-time video processing system featuring a bright, joyful, and modern flat UI. Ingest video frames, detect faces and emotions with MediaPipe, render a live floating emoji HUD, and broadcast to unlimited clients via Redis Pub/Sub.

---

## ✨ What's New in v2.0
- **Joyful UI Design:** Completely redesigned with a warm, flat color palette (Sunrise Orange, Lemon Yellow, Mint Green, and Deep Navy) for a delightful user experience.
- **Real-Time Emotion Detection:** Analyzes facial expressions dynamically and identifies emotions (Happy, Surprise, Angry, Sad, Wink, Neutral).
- **Floating Emoji HUD:** A floating DOM-based HUD displays cheerful emojis reacting to the detected emotion along with contextual supportive text.
- **Optimized Heuristics:** Normalized spatial ratio heuristics mean emotion detection works perfectly regardless of camera distance.

---

## 🚀 Quick Start

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

## 🏗️ Architecture & Data Flow

VisionLink is built for horizontal scalability. Unlike basic implementations that store connections in memory, this system uses a distributed message bus.

### The Life of a Frame:
1.  **Ingest:** A source (camera/script) POSTs a JPEG to `/api/ingest`.
2.  **Process:** Backend validates the `X-API-Key`, runs MediaPipe face & emotion detection, and logs coordinates.
3.  **Persist:** Metadata is sent to a background task. It fetches an atomic ID from a **Postgres Sequence** and saves the record.
4.  **Broadcast:** The rendered JPEG is published to a **Redis channel**.
5.  **Egress:** All connected WebSocket clients (`/api/stream`) receive the frame from Redis and update their views in React.

---

## 📂 File Structure & Responsibilities

### 🔹 Backend (`/backend`)
| File | Responsibility |
| :--- | :--- |
| `app/main.py` | Entry point. Handles lifespan (Redis/DB init) and global error handling. |
| `app/api/ingest.py` | Receives frames. Handles validation, detection triggering, and background saves. |
| `app/api/stream.py` | WebSocket endpoint. Subscribes clients to the Redis frame stream. |
| `app/api/roi.py` | Query API for detection history. Features **Cursor-based pagination**. |
| `app/api/deps.py` | Security layer. Implements API Key validation. |
| `app/core/detector.py` | MediaPipe wrapper. Includes advanced normalized spatial logic for robust emotion heuristics. |
| `app/core/broadcaster.py` | The "Message Bus". Uses Redis Pub/Sub to share frames across workers. |
| `app/db/crud.py` | Database operations. Uses SQL sequences and keyset pagination. |
| `Dockerfile` | Optimized build using **BuildKit cache mounts** for 10x faster builds. |

### 🔹 Frontend (`/frontend`)
| File | Responsibility |
| :--- | :--- |
| `src/App.jsx` | Main dashboard. Manages WebSocket lifecycle, UI state, and the floating emoji HUD. |
| `src/components/` | Reusable UI: `VideoStream`, `RoiCanvas`, `StatsPanel`, `DetectionTimeline`. |
| `src/index.css` | Global styling featuring the bright, clean, flat UI and modern color palette. |
| `Dockerfile` | Nginx-based production build with multi-stage caching. |

### 🔹 Infrastructure
| File | Responsibility |
| :--- | :--- |
| `docker-compose.yml` | Orchestrates Backend, Frontend, Postgres, Redis, and Nginx. |
| `nginx/nginx.conf` | Reverse proxy. Handles WebSocket upgrades and unified `/api/` routing. |

---

## 🔒 Security & Reliability

- **API Key Auth:** The `/api/ingest` endpoint is protected by an `X-API-Key` header to prevent unauthorized resource exhaustion.
- **No Silent Failures:** DB writes use background tasks with `add_done_callback` to ensure persistence errors are logged.
- **Horizontal Scaling:** By using Redis instead of in-memory lists, you can run multiple backend workers and sync state seamlessly.

---

## 🔌 API Reference

### `POST /api/ingest`
Sends a frame for processing.
- **Header:** `X-API-Key: <your_key>` (if enabled)
- **Body:** `multipart/form-data` with `frame` field.

### `GET /api/roi`
Retrieves detection history.
- **Params:** `limit`, `session_id`, `since`, `after` (cursor).
- **Pagination:** Uses `next_cursor` from the response to fetch the next page via `?after=...`.

---

## 🧪 Testing

The system includes comprehensive integration tests covering auth, processing, and pagination.

```bash
# Run all tests in a clean container
docker-compose run --rm backend pytest
```

---

## 🛠️ Technical Choices
- **FastAPI:** High-performance async Python framework.
- **MediaPipe Face Mesh:** State-of-the-art ML for low-latency facial landmark detection.
- **React + Framer Motion:** Joyful frontend animations and reactive UI updates.
- **Redis Pub/Sub:** Industry standard for scalable real-time messaging.
- **PostgreSQL:** Reliable relational storage with strong data integrity.

---

## AI Collaboration Attestation

This project was built with a deliberate and strategic approach to AI collaboration, ensuring that I remained the primary architect and driver of the system. I did not "vibe code" this project; rather, I used AI as a targeted force multiplier.

*   **Backend Engineering (Core Expertise):** As a backend-focused engineer, I designed the system architecture, established the database schema, devised the real-time WebSocket + Redis pub/sub mechanism, and solved the tricky spatial logic required for emotion heuristics without OpenCV. AI was utilized strictly as an advanced autocomplete to quickly scaffold repetitive boilerplate (e.g., Pydantic models, FastAPI route structures, and basic CRUD shells). The core logic, security practices, and structural decisions are entirely my own.
*   **Frontend Development (Enabling Capability):** Since frontend is not my primary domain, I leveraged AI more heavily to generate the React components, CSS styling, and responsive layout. This allowed me to deliver a polished, full-stack, and high-craft UI that meets modern design standards without getting bogged down in CSS intricacies.

**The Takeaway:** This dual approach highlights my ability to use AI pragmatically: as a high-speed assistant in my areas of expertise (to ship faster without losing architectural control), and as a powerful enabler in unfamiliar domains (to deliver complete, end-to-end solutions independently).
