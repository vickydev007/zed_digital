# Open-Set Person Re-Identification under Low Inter-Class Variance

> **Enterprise AI System — Zed Digital**  
> Production-grade deep metric learning framework for person re-identification in real deployments where many individuals wear identical uniforms.

---

## Problem Statement

Standard Re-ID assumes a **closed gallery** with **visually distinct** identities.  
Real deployments fail when:
1. The gallery is **open** — unknown impostors must be rejected.
2. Many enrolled persons wear **identical clothing** — low inter-class appearance variance.

The hard failure mode: **False Accept** — an unenrolled impostor wearing the same uniform is matched to a legitimate enrolled person.

---

## System Architecture

```
Input Crop [256×128]
       │
       ▼
OmniScaleReIDBackbone  (3.73M params)
  ├─ Stem: Conv7×7 → MaxPool → Conv3×3
  ├─ Stage 1: OmniScaleStreamBlock × 2  (128ch, 32×16)
  ├─ Stage 2: OmniScaleStreamBlock × 3  (256ch, 16×8)
  └─ Stage 3: OmniScaleStreamBlock × 2  (384ch, 16×8)
       │
       ▼
DualGranularityReIDHead
  ├─ Global Branch: GeM Pool → FC(384→256) → BNNeck  [256-d]
  ├─ Part Branch:  HorizontalPartAttentivePooling (5 stripes) → FC [256-d]
  └─ OrthogonalProjectionLayer: removes uniform-color subspace
       │
       ▼  L2-normalised 512-d embedding
       │
       ▼
OpenSetMatcher
  ├─ ConfidenceCalibrator (Platt Scaling)
  ├─ CohortCalibrator (Z-Norm: background uniform bias cancellation)
  ├─ EVTTailCalibrator (Weibull tail hypothesis test)
  └─ OpenSetDecisionEngine
       ├─ Score threshold gate
       ├─ Contrast margin gate  ← critical for same-clothing
       └─ EVT tail gate
```

---

## Training Objectives

| Loss Component | Purpose |
|---|---|
| `SubCenterArcFaceLoss` | Hyperspherical angular margin classification (K=2 sub-centers per identity) |
| `AdaptiveHardNegativeTripletLoss` | Batch-hard mining with dynamic margin ∝ attire similarity of hardest negative |
| `PartOrthogonalityLoss` | Ensures 5 body stripes learn non-redundant features |

---

## Quick Start

### 1. Install
```bash
pip install -e .
```

### 2. Run Full Experiment Pipeline
```bash
python run_experiments.py
```
This will:
- Generate a curated low-variance benchmark (navy security uniforms)
- Train 5 ablation configurations (Baseline → Full System)
- Compute ROC, FAR@Recall, TAR@FAR, EER, Rank-1, mAP
- Generate publication-grade figures in `experiments/reports/`
- Export the best model to ONNX
- Profile edge latency and gallery search scaling

### 3. Unit Tests
```bash
python -X utf8 tests/test_architecture.py
python -X utf8 tests/test_openset_modules.py
```

### 4. C++ Inference Benchmark
```bash
cd openset_reid/cpp
mkdir build && cd build
cmake .. && cmake --build . --config Release
.\openset_bench.exe
```

---

## Key Files

| File | Description |
|---|---|
| [`openset_reid/models/backbones.py`](openset_reid/models/backbones.py) | OmniScale multi-scale feature extractor |
| [`openset_reid/models/heads.py`](openset_reid/models/heads.py) | Dual-Granularity head + Orthogonal Projection |
| [`openset_reid/models/loss.py`](openset_reid/models/loss.py) | SubCenterArcFace + Adaptive Triplet Loss |
| [`openset_reid/open_set/calibrator.py`](openset_reid/open_set/calibrator.py) | Full open-set matcher (enrollment + matching) |
| [`openset_reid/open_set/evt_calibration.py`](openset_reid/open_set/evt_calibration.py) | Weibull EVT tail calibration |
| [`openset_reid/open_set/cohort_calibration.py`](openset_reid/open_set/cohort_calibration.py) | Background cohort Z-normalization |
| [`openset_reid/open_set/decision_boundary.py`](openset_reid/open_set/decision_boundary.py) | Multi-criterion open-set decision engine |
| [`openset_reid/evaluation/metrics.py`](openset_reid/evaluation/metrics.py) | ROC, FAR@Recall, TAR@FAR, EER, CMC, mAP |
| [`openset_reid/evaluation/visualisation.py`](openset_reid/evaluation/visualisation.py) | Publication-grade figure generation |
| [`openset_reid/deployment/export_onnx.py`](openset_reid/deployment/export_onnx.py) | ONNX export with numerical parity validation |
| [`openset_reid/deployment/onnx_inference.py`](openset_reid/deployment/onnx_inference.py) | Production ONNX runtime engine |
| [`openset_reid/cpp/src/openset_matcher.cpp`](openset_reid/cpp/src/openset_matcher.cpp) | C++ high-performance matcher (MSVC/GCC) |
| [`run_experiments.py`](run_experiments.py) | Master pipeline orchestrator |

---

## Evaluation Metrics

| Metric | Description |
|---|---|
| **FAR @ Rec=90/95%** | Primary metric: false accept rate at fixed recall |
| **TAR @ FAR=0.1/1%** | True accept rate at fixed false accept budget |
| **EER** | Equal error rate (FAR = FRR operating point) |
| **ROC AUC** | Area under the ROC curve |
| **Rank-1 / mAP** | Closed-set retrieval accuracy |
| **ECE / Brier Score** | Confidence calibration quality |

---

## Hardware Requirements

| Mode | Requirement |
|---|---|
| **Training (CPU)** | 8GB RAM, ~15 min for 12-epoch demo |
| **Training (GPU)** | RTX 2050+ (4GB VRAM), ~8 min at 80 epochs |
| **Inference (CPU)** | < 10ms per crop on modern laptop CPU |
| **C++ Benchmark** | ~0.25ms per query on 1000-gallery (MSVC /O2) |

---

*© 2026 Zed Digital AI Engineering — Enterprise Re-ID System*
