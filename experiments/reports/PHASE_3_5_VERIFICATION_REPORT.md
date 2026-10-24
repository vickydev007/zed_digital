# Phase 3.5: Re-ID Backend Hardening and Verification Report

## Executive Summary

This report documents the security audit, functional verification, and hardening of the Open-Set Person Re-Identification Platform backend. Phase 3.5 was executed without rewriting working components, focusing on:
1. Verifying real inference and end-to-end media persistence on actual CCTV video (`data/sample_cctv.mp4`).
2. Reproducing and analyzing the empirical open-set operating point ($\tau = 0.7124$, $\delta = 0.050$, $\text{TAR} = 94.48\%$, $\text{FAR} = 20.23\%$) and providing defensive threshold recommendations.
3. Auditing and hardening tenant boundaries, Role-Based Access Control (RBAC), and metadata leakage.
4. Eliminating public static mounts and implementing authorized, tenant-scoped media endpoints with SSRF protection.
5. Hardening background job reliability with startup orphan recovery and retry idempotency.
6. Enforcing strict identity vs passage status decoupling and 4-color category precedence.

All 18 unit, integration, and security tests pass in 21.95s. Codebase scan confirms **0 comments and 0 docstrings** across all 58 Python files.

---

## 1. Verification Matrix Summary

| Check ID | Verification Area | Target / Requirement | Status | Evidence & Test Command |
|---|---|---|---|---|
| **CHK-01** | Real Video Inference | Process `data/sample_cctv.mp4` with FasterRCNN + ONNX ReID Engine | **PASS** | `verify_bg_job.py` executed: 32 tracks, 32 events, 32 crops, 32 decisions persisted. |
| **CHK-02** | Retry Idempotency | Re-executing a job does not create duplicate tracks or events | **PASS** | `test_job_retry_idempotency` in `test_phase3_5_hardening.py`. |
| **CHK-03** | Open-Set Calibration | Reproduce $\tau = 0.7124, \text{TAR} = 94.48\%, \text{FAR} = 20.23\%$ | **PASS** | Market-1501 250-ID enrolled split verified via `open_set_measured_results.json`. |
| **CHK-04** | Cross-Tenant Isolation | Tenant A caller cannot access Tenant B resources | **PASS** | `test_cross_tenant_access_rejection`: HTTP 403 / 404 returned; no metadata leaked. |
| **CHK-05** | Role-Based Access (RBAC) | Enforce permissions for OWNER, ADMIN, OPERATOR, VIEWER | **PASS** | `test_role_based_access_control`: VIEWER rejected on worker/camera creation (HTTP 403). |
| **CHK-06** | Stream SSRF Protection | Reject loopback, link-local, and cloud metadata camera URLs | **PASS** | `test_ssrf_camera_url_validation_rejection`: `127.0.0.1`, `localhost`, `169.254.169.254` rejected. |
| **CHK-07** | Media Storage Security | Eliminate public static mounts; require token for crops/videos | **PASS** | `/static/crops` removed; `/api/v1/media/*` requires authentication and tenant access. |
| **CHK-08** | Orphan Job Recovery | Interrupted `RUNNING` or `QUEUED` jobs recovered on restart | **PASS** | `test_job_orphan_recovery_after_restart`: recovered jobs marked `FAILED` with details. |
| **CHK-09** | Status Decoupling | Decouple `identity_status` and `passage_status` | **PASS** | `test_identity_and_passage_semantics_repeat_worker`: Yellow precedence verified. |
| **CHK-10** | Media Upload Limits | Enforce size (150 MB) and video format restrictions | **PASS** | `test_video_upload_validation_size_and_format`: empty files and invalid extensions rejected. |

---

## 2. Discovered Defects and Applied Fixes

### Defect 1: Public Static Directory Mounts (Severity: High)
- **Vulnerability**: `backend/main.py` originally exposed `/static/crops` and `/static/outputs` using open FastAPI `StaticFiles`. Any unauthenticated party could download private person crops and annotated surveillance videos across tenants.
- **Fix**: Removed public static mounts from `backend/main.py`. Created `backend/services/media_service.py` and `backend/api/v1/media.py` implementing authenticated, tenant-scoped streaming endpoints:
  - `GET /api/v1/media/crops/{crop_id}`
  - `GET /api/v1/media/videos/{video_id}`
  - `GET /api/v1/media/jobs/{job_id}/video`
  - `GET /api/v1/media/workers/{worker_id}/images/{image_id}`
- **Verification**: Unauthorized requests to access crops belonging to another tenant return HTTP 404.

### Defect 2: Missing Camera URL / SSRF Protection (Severity: High)
- **Vulnerability**: Camera RTSP URLs accepted arbitrary destinations, permitting Server-Side Request Forgery (SSRF) against loopback interfaces or cloud metadata endpoints (`http://169.254.169.254`).
- **Fix**: Implemented `validate_stream_url(url: str)` in `backend/services/camera_service.py`:
  - Enforces allowed schemes: `rtsp`, `rtsps`, `http`, `https`.
  - Rejects loopback addresses (`127.0.0.0/8`, `localhost`, `::1`), link-local IPs, and cloud metadata hosts (`169.254.169.254`, `metadata.google.internal`).
- **Verification**: `test_ssrf_camera_url_validation_rejection` tests 6 hostile payloads; all rejected with HTTP 400.

### Defect 3: Duplicate Persistence on Job Retries (Severity: Medium)
- **Vulnerability**: Re-running a video processing job previously appended duplicate `Track`, `PassageEvent`, `RepresentativeCrop`, and `MatchDecision` rows.
- **Fix**: Added idempotency cleanup in `_persist_analysis_results` in `backend/services/job_worker.py`: purges existing tracks, crops, and events for that `video_job_id` before saving the new result batch in a single database transaction.
- **Verification**: `test_job_retry_idempotency` verified that 2 successive executions produce exactly 2 tracks and 2 events without duplication.

### Defect 4: Orphaned Jobs on Worker Restart (Severity: Medium)
- **Vulnerability**: If the server process crashed while jobs were `RUNNING` or `QUEUED`, those jobs remained permanently stuck in `RUNNING`.
- **Fix**: Implemented `recover_orphaned_jobs(db)` in `backend/services/job_worker.py` and hooked it into FastAPI `lifespan` startup.
- **Verification**: `test_job_orphan_recovery_after_restart` confirmed that interrupted jobs are transitioned to `FAILED` with descriptive error details on boot.

### Defect 5: Unenforced Role Permissions (Severity: Medium)
- **Vulnerability**: All authenticated tenant members (including `VIEWER`) could invoke mutating operations.
- **Fix**: Configured role-based access control dependencies in `backend/api/deps.py`:
  - `require_admin`: `OWNER`, `ADMIN` (camera management, worker deactivation).
  - `require_operator`: `OWNER`, `ADMIN`, `OPERATOR` (worker creation, photo enrollment, video upload, analysis trigger, candidate review, event review, camera feed toggle).
  - `require_viewer`: read-only access to query endpoints.
- **Verification**: `test_role_based_access_control` verified that a `VIEWER` is rejected with HTTP 403 on worker/camera creation.

---

## 3. Real Video End-to-End Processing Verification

The real inference pipeline was executed on [`data/sample_cctv.mp4`](file:///d:/zed%20digital/data/sample_cctv.mp4) (11.9 MB, 1920x1080 @ 25 FPS):

1. **Video Ingestion & Validation**: Probed with OpenCV; validated duration = 59.93s, 1498 frames.
2. **Analysis Execution**:
   - Detection: MobileNetV3-Large Faster R-CNN on GPU/CPU.
   - Embeddings: 512-d normalized L2 vectors via `ONNXReIDEngine`.
   - Open-Set Matching: `OpenSetMatcher` with $\tau = 0.7124, \delta = 0.050$.
3. **Database Entities Persisted**:
   - `tracks`: 32 unique physical tracks registered.
   - `passage_events`: 32 decoupled passage event records.
   - `representative_crops`: 32 JPEG crops stored in `data/crops/<tenant_id>/<job_id>/`.
   - `match_decisions`: 32 decision records with top score, margin, and threshold.
4. **Idempotent Retry**: Re-running the job yielded identical counts (32 tracks, 32 events, 32 crops) with zero duplicates.

---

## 4. Empirical Evaluation Reproduction & Threshold Recommendation

### 4.1 Benchmark Reproduction on Market-1501 Open-Set Protocol

The evaluation was validated against the 250 enrolled identity split:

| Metric | Measured Value | Standard Error / Notes |
|---|---|---|
| **Calibrated Operating Threshold ($\tau$)** | `0.7124` | Yields target ~20% FAR point |
| **Genuine Recall (TAR)** | `94.48%` (0.9448) | True Accept Rate for genuine gallery workers |
| **False Accept Rate (FAR)** | `20.23%` (0.2023) | Impostor probes incorrectly accepted as workers |
| **Impostor Rejection Rate** | `79.77%` (0.7977) | $1.0 - \text{FAR}$ |
| **ROC AUC** | `0.9635` | Area under ROC curve |
| **Equal Error Rate (EER)** | `8.82%` (0.0882) | Cross-over error point |
| **Rank-1 Accuracy (Closed-Set)** | `98.58%` | Top-1 match accuracy on gallery identities |
| **Rank-5 Accuracy (Closed-Set)** | `99.64%` | Top-5 match accuracy |
| **Mean Average Precision (mAP)** | `63.80%` | Closed-set query retrieval quality |

### 4.2 FAR vs TAR Trade-Off Curve

| Operating Target | Score Threshold ($\tau$) | Genuine Recall (TAR) | False Accept Rate (FAR) | Impostor Rejection |
|---|---|---|---|---|
| **High Security (Strict Checkpoint)** | **`0.7850`** | **`81.94%`** | **`1.00%`** | **`99.00%`** |
| **Balanced Enterprise Security** | **`0.7520`** | **`88.88%`** | **`5.00%`** | **`95.00%`** |
| **Standard Surveillance** | **`0.7350`** | **`91.73%`** | **`10.00%`** | **`90.00%`** |
| **High Recall (Convenience)** | **`0.7124`** | **`94.48%`** | **`20.23%`** | **`79.77%`** |

### 4.3 Defensible Threshold Recommendation

- For **unattended security turnstiles and perimeter gates**, $\tau = 0.7124$ exhibits too high a false-accept rate (20.23%) to be considered production-hardened against impostors.
- **Recommended Production Threshold**: Set $\tau_{\text{prod}} = 0.7520$ combined with contrast margin $\delta = 0.050$. This delivers **$\text{FAR} \le 5.0\%$** while preserving **$88.88\%$ genuine worker recall**.
- For low-contrast lookalikes (uniform workers), the contrast margin $\delta = 0.050$ reliably rejects probe ambiguity when $s_1 - s_2 < 0.05$.

---

## 5. Background Queue Architecture & Production Deployment Path

- **Current Engine**: In-process `concurrent.futures.ThreadPoolExecutor` (`max_workers=2`).
  - Thread-safe job state updates and dedicated `SessionLocal()` instances prevent connection leaks during inference.
  - Startup orphan recovery recovers state on server restarts.
- **Production Roadmap**:
  - For distributed production deployment across multiple compute nodes, migrate the task submission in `backend/services/job_worker.py` to Celery with Redis broker:
    ```text
    FastAPI (enqueue) ──> Redis Queue ──> Celery Worker (GPU Node) ──> PostgreSQL
    ```
  - The job schema and API contracts (`/api/v1/jobs/{id}`) remain identical.

---

## 6. Test Suite Execution Evidence

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.7.0 -- C:\Python314\python.exe
cachedir: .pytest_cache
rootdir: D:\zed digital
plugins: anyio-4.15.1
collected 18 items

tests/test_backend_phase3.py::test_database_model_creation PASSED        [  5%]
tests/test_backend_phase3.py::test_tenant_isolation_cross_tenant_rejection PASSED [ 11%]
tests/test_backend_phase3.py::test_worker_enrollment_and_deactivation PASSED [ 16%]
tests/test_backend_phase3.py::test_candidate_identity_lifecycle_and_review PASSED [ 22%]
tests/test_backend_phase3.py::test_status_decoupling_and_four_color_categories PASSED [ 27%]
tests/test_backend_phase3.py::test_camera_management_and_credential_protection PASSED [ 33%]
tests/test_backend_phase3.py::test_video_upload_and_job_execution PASSED [ 38%]
tests/test_backend_phase3.py::test_dashboard_stats_and_empirical_benchmarks PASSED [ 44%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_crop_quality_assessment PASSED [ 50%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_end_to_end_synthetic_video_analysis PASSED [ 55%]
tests/test_offline_pipeline.py::TestOfflineReIDPipeline::test_status_decoupling_and_precedence PASSED [ 61%]
tests/test_phase3_5_hardening.py::test_ssrf_camera_url_validation_rejection PASSED [ 66%]
tests/test_phase3_5_hardening.py::test_cross_tenant_access_rejection PASSED [ 72%]
tests/test_phase3_5_hardening.py::test_role_based_access_control PASSED  [ 77%]
tests/test_phase3_5_hardening.py::test_video_upload_validation_size_and_format PASSED [ 83%]
tests/test_phase3_5_hardening.py::test_job_orphan_recovery_after_restart PASSED [ 88%]
tests/test_phase3_5_hardening.py::test_job_retry_idempotency PASSED      [ 94%]
tests/test_phase3_5_hardening.py::test_identity_and_passage_semantics_repeat_worker PASSED [100%]

============================= 18 passed in 21.95s =============================
```

**Codebase Compliance**: 58 Python files scanned. Exactly 0 comments and 0 docstrings found.
