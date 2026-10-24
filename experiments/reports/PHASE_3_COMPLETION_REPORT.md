# Phase 3 Completion Report: Re-ID Backend and Database Architecture

## 1. Executive Summary

Phase 3 of the Open-Set Person Re-Identification Platform is complete. A multi-tenant database layer and asynchronous REST API backend have been implemented using FastAPI, SQLAlchemy 2.x ORM, Alembic migrations, and Pydantic v2 schemas.

The system connects to the offline inference engine (`openset_reid.pipeline.video_analyzer.OfflineVideoAnalyzer`), preserving the calibrated operating point ($\tau = 0.7124$, $\delta = 0.050$, 94.48% genuine recall at 20.23% FAR).

All 11 unit and integration tests pass with zero warnings, zero comments, and zero docstrings across all 55 codebase files.

---

## 2. Database Schema & Architecture

The database architecture is designed for production multi-tenant deployments on PostgreSQL (with portable SQLite dialect support for development and test execution).

### 2.1 Entity Model (20 Tables)

| Entity Domain | Table Name | Purpose | Primary / Foreign Keys & Indexes |
|---|---|---|---|
| **Tenancy & Auth** | `tenants` | Organization / facility isolation boundary | PK `id`, unique index `slug` |
| | `users` | Authenticated operators and administrators | PK `id`, unique index `email` |
| | `tenant_memberships` | Role-based tenant authorization (`OWNER`, `ADMIN`, `OPERATOR`, `VIEWER`) | PK `id`, FK `tenant_id`, FK `user_id`, unique (`tenant_id`, `user_id`) |
| **Surveillance Devices** | `cameras` | CCTV and IP camera stream metadata | PK `id`, FK `tenant_id`, indexed `tenant_id` |
| | `camera_credentials` | Encrypted RTSP connection secrets (Fernet encrypted) | PK `id`, FK `camera_id` |
| **Enrolled Personnel** | `workers` | Stable enrolled worker directory | PK `id`, FK `tenant_id`, unique (`tenant_id`, `staff_code`) |
| | `enrollment_images` | Verified reference crops with Laplacian blur quality scores | PK `id`, FK `worker_id` |
| | `person_embeddings` | 512-dimensional normalized embeddings extracted via ONNX engine | PK `id`, FK `tenant_id`, FK `worker_id`, FK `candidate_identity_id` |
| **Provisional Identities** | `candidate_identities` | Unenrolled repeat visitors and new person candidates | PK `id`, FK `tenant_id`, unique (`tenant_id`, `candidate_code`) |
| **Media Assets & Jobs** | `video_assets` | Validated video file uploads and format metadata | PK `id`, FK `tenant_id`, FK `camera_id` |
| | `video_jobs` | Asynchronous inference execution records and state | PK `id`, FK `tenant_id`, FK `video_asset_id`, indexed `status` |
| **Kinematic Tracking** | `tracks` | Trajectory spans from entrance to exit | PK `id`, FK `tenant_id`, FK `video_job_id`, FK `camera_id` |
| | `observations` | Per-frame bounding box coordinates and quality metrics | PK `id`, FK `tenant_id`, FK `track_id` |
| | `match_decisions` | Open-set score telemetry ($s_1, s_2, \delta, \tau$) and accept/reject decisions | PK `id`, FK `tenant_id`, FK `track_id` |
| **Passage & Presence** | `passage_events` | Granular physical transit records with decoupled statuses | PK `id`, FK `tenant_id`, FK `video_job_id`, FK `track_id`, FK `worker_id` |
| | `presence_sessions` | Continuous facility occupancy tracking with repeat passage counters | PK `id`, FK `tenant_id`, FK `worker_id`, FK `candidate_identity_id` |
| **Visual Artifacts** | `representative_crops` | Quality-approved person crops ($h \ge 28$, $w \ge 12$, blur $\ge 30$) | PK `id`, FK `tenant_id`, FK `track_id`, FK `passage_event_id` |
| **Audit & Governance** | `audit_logs` | Immutable audit trail for enrollment, review, and deletion | PK `id`, FK `tenant_id`, FK `user_id`, indexed `action` |
| **Empirical Science** | `experiment_runs` | Persistent benchmark execution metadata and calibration parameters | PK `id`, FK `tenant_id`, indexed `experiment_name` |
| | `evaluation_results` | Measured statistical metrics (FAR, TAR, EER, AUC, mAP, Rank-1) | PK `id`, FK `experiment_run_id` |

### 2.2 Migrations

Alembic migration `e091821c746a_initial_schema.py` defines all 20 tables, constraints, foreign keys, and indexes. It supports both PostgreSQL (using native `JSONB`) and SQLite (using `JSON` with batch alter table).

---

## 3. Status Decoupling & Display Category Precedence

To eliminate conflation between an individual's verified identity and their physical transit events, `identity_status` and `passage_status` are decoupled:

### 3.1 Field Definitions

- **`identity_status`**:
  - `OFFICIAL_WORKER`: Verified match against enrolled gallery ($s_1 \ge \tau$ and $s_1 - s_2 \ge \delta$).
  - `NEW_CANDIDATE`: Unenrolled person whose crop passed quality filters ($h \ge 28, w \ge 12, \text{blur} \ge 30$).
  - `UNKNOWN`: Unmatched or low-quality crop below acceptance criteria.
- **`passage_status`**:
  - `FIRST_ENTRY`: First appearance of an identity during the observation window.
  - `PASSAGE_IN_PROGRESS`: Continuous active tracking across frames ($10 \le \text{frames} < 25$).
  - `ALREADY_PASSED`: Completed passage sequence ($\text{frames} \ge 25$).
  - `REPEAT_PASSAGE`: Subsequent transit by an identity previously registered in the session.

### 3.2 Display Precedence & Color Mapping

```text
if passage_status == REPEAT_PASSAGE:
    display_category = PREVIOUSLY_ENROLLED (YELLOW)
elif identity_status == OFFICIAL_WORKER:
    display_category = OFFICIAL_WORKER (GREEN)
elif identity_status == NEW_CANDIDATE:
    display_category = NEW_PERSON (BLUE)
else:
    display_category = UNKNOWN (RED)
```

**Precedence Invariant**: A returning official worker receives the **Yellow** (`PREVIOUSLY_ENROLLED`) visual badge on surveillance monitors to alert security to a repeat transit event, while internally retaining `identity_status = OFFICIAL_WORKER`, ensuring audit accuracy and preventing duplicate worker creation.

---

## 4. Multi-Tenant Security & Access Control

1. **Tenant-Scoped Authorization**: Every API request evaluates the caller's JWT bearer token against `TenantMembership`. Cross-tenant requests return `403 Forbidden`.
2. **Resource Scoping**: All database queries filter by `tenant_id`. Direct object access across tenants returns `404 Not Found` or `403 Forbidden`.
3. **Camera Credential Encryption**: RTSP passwords and streaming URLs are encrypted at rest using AES-128-CBC / HMAC-SHA256 (Fernet) via `backend.core.security`. Ordinary API responses return only sanitized metadata (`has_encrypted_stream: true`) and never expose credentials.
4. **Audit Logging**: Sensitive mutations (`CREATE_WORKER`, `ENROLL_WORKER_IMAGE`, `DEACTIVATE_WORKER`, `REVIEW_CANDIDATE`, `DELETE_CAMERA`) write immutable records to `audit_logs`.

---

## 5. Asynchronous Video Processing Queue

Video analysis requests return HTTP `202 Accepted` immediately with a persistent `video_job_id`. Long-running inference is handled asynchronously:

```text
Upload Video -> Probe Media -> Create VideoAsset -> Enqueue Job (QUEUED)
                                                          │
                                                    Worker Thread
                                                          ▼
                                                    Update RUNNING
                                                          │
                                           Load Enrolled Embeddings
                                                          │
                                         Run OfflineVideoAnalyzer
                                           (Check Cancellation)
                                                          │
                                          Persist Database Entities
                                          - Tracks
                                          - Observations
                                          - Representative Crops
                                          - Passage Events
                                          - Presence Sessions
                                          - Match Decisions
                                                          ▼
                                                    Update COMPLETED
```

Database transactions are scoped strictly to job state updates and final persistence batches, ensuring no database connections are held open during model inference.

---

## 6. FastAPI Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Authenticate user, return JWT token & accessible tenants |
| `POST` | `/api/v1/auth/register` | Register new user account |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `GET` | `/api/v1/auth/tenants` | List tenants accessible to caller |
| `POST` | `/api/v1/auth/tenants` | Create new tenant and assign ownership |
| `GET` | `/api/v1/workers` | List tenant workers with pagination, search, and department filter |
| `POST` | `/api/v1/workers` | Create new worker |
| `GET` | `/api/v1/workers/{id}` | Retrieve worker detail and enrollment photos |
| `PATCH` | `/api/v1/workers/{id}` | Update worker information |
| `POST` | `/api/v1/workers/{id}/deactivate` | Deactivate worker |
| `POST` | `/api/v1/workers/{id}/enroll` | Upload reference image, assess quality, extract 512-d embedding |
| `GET` | `/api/v1/cameras` | List tenant cameras |
| `POST` | `/api/v1/cameras` | Create camera and encrypt credentials |
| `GET` | `/api/v1/cameras/{id}` | Retrieve camera status |
| `PATCH` | `/api/v1/cameras/{id}` | Update camera |
| `DELETE` | `/api/v1/cameras/{id}` | Delete camera |
| `POST` | `/api/v1/cameras/{id}/start` | Activate camera stream |
| `POST` | `/api/v1/cameras/{id}/stop` | Deactivate camera stream |
| `POST` | `/api/v1/videos/upload` | Upload and validate video file |
| `GET` | `/api/v1/videos` | List video assets |
| `GET` | `/api/v1/videos/{id}` | Retrieve video metadata |
| `POST` | `/api/v1/videos/{id}/analyze` | Enqueue asynchronous offline Re-ID analysis |
| `GET` | `/api/v1/jobs` | List processing jobs |
| `GET` | `/api/v1/jobs/{id}` | Retrieve job status and telemetry summary |
| `GET` | `/api/v1/jobs/{id}/progress` | Lightweight polling endpoint for progress percentage |
| `POST` | `/api/v1/jobs/{id}/cancel` | Cancel in-progress or queued job |
| `GET` | `/api/v1/candidates` | List provisional candidate identities |
| `GET` | `/api/v1/candidates/{id}` | Candidate identity detail |
| `POST` | `/api/v1/candidates/{id}/review` | Review candidate (approve, reject, merge) |
| `GET` | `/api/v1/passage/events` | Query passage events with 4-category filtering |
| `GET` | `/api/v1/passage/events/{id}` | Event detail |
| `POST` | `/api/v1/passage/events/{id}/review` | Review passage event |
| `GET` | `/api/v1/passage/presence` | List currently present workers and candidates |
| `GET` | `/api/v1/dashboard/stats` | Unified dashboard counters and 4-category distribution |
| `GET` | `/api/v1/evaluation/benchmarks` | Retrieve empirical Market-1501 benchmark results |
| `GET` | `/api/v1/evaluation/experiments` | List persistent experiment runs |
| `POST` | `/api/v1/evaluation/experiments/seed` | Seed Phase 2 benchmark record |

---

## 7. Empirical Validation & Research Integrity

All benchmark figures returned by `/api/v1/evaluation/benchmarks` and persisted in `experiment_runs` match the empirical Phase 2 measurement:

- **Calibrated Operating Threshold**: $\tau = 0.7124$
- **Contrast Margin**: $\delta = 0.050$
- **Genuine Recall (TAR)**: $94.48\%$
- **False Accept Rate (FAR)**: $20.23\%$
- **Impostor Rejection Rate**: $79.77\%$
- **Receiver Operating Characteristic (ROC AUC)**: $0.9635$
- **Equal Error Rate (EER)**: $8.82\%$
- **Cumulative Match Characteristic (Rank-1 / Rank-5)**: $98.58\% / 99.64\%$
- **Mean Average Precision (mAP)**: $63.80\%$
- **Inference Latency**: 5.86 ms (ONNX Runtime) vs 9.24 ms (PyTorch)

---

## 8. Test Suite Results

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\zed digital
plugins: anyio-4.15.1
collected 11 items

tests/test_backend_phase3.py::test_database_model_creation PASSED        [  9%]
tests/test_backend_phase3.py::test_tenant_isolation_cross_tenant_rejection PASSED [ 18%]
tests/test_backend_phase3.py::test_worker_enrollment_and_deactivation PASSED [ 27%]
tests/test_backend_phase3.py::test_candidate_identity_lifecycle_and_review PASSED [ 36%]
tests/test_backend_phase3.py::test_status_decoupling_and_four_color_categories PASSED [ 45%]
tests/test_backend_phase3.py::test_camera_management_and_credential_protection PASSED [ 54%]
tests/test_backend_phase3.py::test_video_upload_and_job_execution PASSED [ 63%]
tests/test_backend_phase3.py::test_dashboard_stats_and_empirical_benchmarks PASSED [ 72%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_crop_quality_assessment PASSED [ 81%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_end_to_end_synthetic_video_analysis PASSED [ 90%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_status_decoupling_and_precedence PASSED [100%]

============================= 11 passed in 15.79s =============================
```

**Codebase Comment Audit**: Scanned 55 Python files across `backend/`, `alembic/`, `openset_reid/`, and `tests/`. Found 0 comments and 0 docstrings.
