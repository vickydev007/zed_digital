# ZED DIGITAL — Open-Set Person Re-Identification Platform

Enterprise platform for person re-identification under low inter-class variance (identical uniforms), live CCTV stream ingestion, video upload analytics, and decoupled passage tracking.

---

## Quickstart

### 1. Backend API (FastAPI)

```bash
# Start backend server on port 8001
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

- API Docs: `http://localhost:8001/docs`
- Health Check: `http://localhost:8001/health`

### 2. Frontend Application (Next.js)

```bash
cd frontend

# Production mode
npm run start -- -p 3000

# Or development mode
npm run dev
```

- Web UI: `http://localhost:3000`
- Default Administrator Credentials:
  - **Email:** `admin@zeddigital.com`
  - **Password:** `Admin@123456`

---

## Core Features & Usage

### 1. Operations Dashboard (`/`)
- **Key Metrics:** Live counts for Active Official Workers, Qualifying Candidates, Repeat Passages, and Unknown Observations.
- **Visual Category Hierarchy:**
  - 🟢 **Official Worker:** Gallery-verified authorized personnel.
  - 🟡 **Qualifying Candidate:** Unassigned identity with multiple consistent detections.
  - 🔵 **Repeat Passage:** Transient recurrence across cameras.
  - ⚪ **Unknown:** Single-observation unverified detection.
- **Activity Feed:** Real-time passage log with camera IDs and match confidence scores.

### 2. CCTV Camera Streams (`/cameras`)
- **Register Camera:** Enter camera name, location, and RTSP stream URL (`rtsp://user:pass@host:554/stream`).
- **Encrypted Credentials:** RTSP URLs encrypted at rest using AES Fernet.
- **Test Connection:** Validates stream reachability before saving.
- **Live Monitor Modal:** Scoped JWT preview tokens deliver authenticated MJPEG stream with sub-second latency HUD and 4-category detection boxes.

### 3. Video Uploads & Jobs (`/videos`)
- **Upload Video:** Drag-and-drop CCTV video files (MP4, AVI, MOV up to 150 MB).
- **Background Worker:** Analyzes pedestrian crops, extracts 512-d embeddings via ONNX Runtime, and tracks multi-frame consensus.
- **Job Status:** Real-time progress tracking (`PENDING` → `PROCESSING` → `COMPLETED`).
- **Results:** Download annotated video with bounding boxes and view representative person crops.

### 4. Passage Events & Presence (`/passage`)
- **Passage Events:** Timestamped camera transit logs, entry/exit directionality, and similarity scores.
- **Presence Sessions:** Active dwell time tracking per worker across facility zones.
- **Filters:** Query by date range, camera location, or identity name.

### 5. Worker Directory & Candidate Review (`/workers` & `/candidates`)
- **Worker Enrollment:** Register authorized personnel with reference portrait crops.
- **Candidate Review:** High-confidence recurrent unknown persons flagged for supervisor approval or rejection.
- **1-Click Promotion:** Convert vetted candidates into official enrolled workers.

### 6. Empirical Evaluation (`/evaluation`)
- **Market-1501 Benchmark:** 6-camera open-set evaluation matrices.
- **Operational Metrics:** ROC AUC (0.9635), Rank-1 Accuracy (98.58%), and False Accept Rate curves.

---

## Operational Risk Policies

| Policy ID | Score Threshold ($\tau$) | Contrast Margin ($\delta$) | Consensus ($k$) | Operational Gate |
| :--- | :---: | :---: | :---: | :--- |
| `POL-ALERTING-V1` | **0.85** | **0.10** | **$\ge 3$ frames** | **ACTIVE (Default)** — CCTV security alerts |
| `POL-SUPERVISED-V1` | 0.70 | 0.04 | $\ge 1$ frame | Verification with human operator |
| `POL-AUTONOMOUS-V1` | 0.88 | 0.12 | $\ge 5$ frames | **RESTRICTED / BLOCKED** — Safety locked |

---

## Offline Video Analysis (CLI)

Analyze pre-recorded CCTV footage directly via command line:

```bash
python analyze_offline_video.py \
  --video data/sample_cctv.mp4 \
  --output-video data/sample_cctv_annotated.mp4 \
  --crops-dir data/crops/sample_run \
  --output-json experiments/reports/offline_analysis.json \
  --tau 0.85 \
  --margin 0.10
```

---

## Testing & Quality Assurance

```bash
# Run backend pytest suite (88 tests)
python -m pytest tests/ -k "not test_offline_pipeline"

# Run frontend Vitest suite (18 tests)
cd frontend && npm test

# Build production frontend bundle
cd frontend && npm run build
```

---

## Tech Stack

- **Frontend:** Next.js 16 (App Router, Turbopack, React 19, TypeScript)
- **Backend:** FastAPI, Python 3.14, SQLAlchemy, Alembic, Uvicorn
- **AI / ML:** ONNX Runtime (`openset_reid_v5.onnx`), OpenCV, NumPy, scikit-learn
- **Database:** SQLite 3 (WAL mode) / PostgreSQL compatible
- **Security:** AES-Fernet encrypted RTSP credentials, scoped JWT preview tokens, SSRF protection
