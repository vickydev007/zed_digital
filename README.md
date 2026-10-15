# Open-Set Person Re-Identification Under Low Inter-Class Variance (PS-1)

> **Enterprise AI Engineering · Zed Digital**  
> Production-grade open-set person re-identification framework designed for high-security environments where individuals wear identical uniforms, validated on real-world multi-camera Market-1501 surveillance data.

---

## Executive Highlights

- **Target False Accept Rate Calibrated:** Calibrated at $\tau = 0.7124 \implies \mathbf{20.23\%}$ **False Accept Rate** with $\mathbf{94.48\%}$ **Genuine Employee Recall**, rejecting $\mathbf{79.77\%}$ of unknown impostor attempts.
- **Market-1501 Real-World Validation:**
  - **ROC AUC:** $\mathbf{0.6718 \to 0.9635}$ ($+29.17\text{ pp}$ improvement)
  - **Equal Error Rate (EER):** $\mathbf{37.07\% \to 8.82\%}$ ($76.2\%$ error reduction)
  - **FAR @ Recall = 90%:** $\mathbf{95.63\% \to 6.46\%}$ ($93.2\%$ reduction in false alarms)
  - **Closed-Set Rank-1:** $\mathbf{70.46\% \to 98.58\%}$ ($+28.12\text{ pp}$)
  - **Mean Average Precision (mAP):** $\mathbf{10.79\% \to 63.80\%}$ ($+53.01\text{ pp}$)
- **Compact Edge Architecture:** 3.73M parameter OmniScale backbone running at **75.2 FPS** ($13.3\text{ ms}$) on ONNX CPU and **1.8 ms** on NVIDIA GeForce RTX 2050 GPU with verified numerical parity ($5.96 \times 10^{-8}$ max diff).
- **High-Performance C++ Matcher:** Compares probe queries against 1,000 enrolled gallery templates in **0.28 ms** ($>3,500\text{ queries/sec}$).

---

## Presentation & Defense Deliverables

| Deliverable | Description | Location |
| :--- | :--- | :--- |
| **HR & Recruiter Project Guide** | Plain-English project explanation, tech stack matrix, resume bullets, and HR Q&A playbook | [`HR_PROJECT_EXPLANATION.md`](file:///d:/zed%20digital/HR_PROJECT_EXPLANATION.md) |
| **Interactive Presentation Deck** | 12-slide executive presentation with keyboard navigation, slide counter, and speaker notes | [`presentation.html`](file:///d:/zed%20digital/presentation.html) |
| **Interactive Analytics Dashboard** | Real-time browser dashboard featuring Market-1501 Before vs After tabs, dynamic FAR simulator, and live verification | [`dashboard.html`](file:///d:/zed%20digital/dashboard.html) |
| **Technical Defense & Interview Guide** | Complete script, elevator pitches, 20 deep-dive technical Q&As, and live demonstration runbook | [`PRESENTATION_AND_DEFENSE_GUIDE.md`](file:///d:/zed%20digital/PRESENTATION_AND_DEFENSE_GUIDE.md) |
| **Live Camera Stream Pipeline** | Production Python script supporting USB webcams, RTSP IP cameras, and CCTV video recordings | [`realtime_camera_reid.py`](file:///d:/zed%20digital/realtime_camera_reid.py) |
| **Publication Visualizations** | Publication-grade ROC curves, metric comparisons, and KDE score separability plots | [`experiments/reports/`](file:///d:/zed%20digital/experiments/reports/) |

---

## System Architecture

```
Input Frame / Pedestrian Crop [256×128×3]
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
  ├─ Global Branch: Generalized Mean (GeM) Pooling → FC(384→256) → BNNeck  [256-d]
  ├─ Part Branch: 5-Stripe Horizontal Part Attention → FC(384→256)           [256-d]
  └─ Attire Orthogonal Subspace Projection: strips uniform color bias
       │
       ▼  L2-Normalized 512-d Unit Embedding
       │
       ▼
OpenSetMatcher (3-Gate Decision Cascade)
  ├─ Gate 1: Raw Cosine Similarity Threshold (s >= 0.7124)
  ├─ Gate 2: Contrast Margin (s1 - s2 >= 0.05) ← Blocks identical-uniform impostors
  ├─ Gate 3: Extreme Value Theory (EVT) Weibull Tail Rejection
  └─ Confidence Calibrator: Platt Scaling Posterior Match Probability
```

---

## Deep Metric Learning Objectives

1. **Sub-Center ArcFace Loss ($K=2$, $m=0.35$):** Assigns 2 sub-centers per identity on hyperspherical geometry, naturally absorbing front/back viewpoints and posture variations while maintaining an angular boundary between classes.
2. **Attire-Aware Adaptive Triplet Loss:** Dynamically increases triplet repulsive margin when negative candidates wear similar uniform attire:
   $$\text{Margin}_{\text{dynamic}} = m_{\text{base}} + \alpha \cdot \text{AttireSimilarity}(a, n)$$
3. **Part Orthogonality Loss:** Penalizes correlation between adjacent horizontal stripe features to force complementary learning across body regions.

---

## Real-World Multi-Camera Benchmark: Market-1501

Tested on the 6-camera outdoor Market-1501 dataset under an open-set protocol:
- **Enrolled Gallery:** 250 identities ($7,055$ reference images)
- **Genuine Probes:** 1,124 queries from enrolled IDs across alternate camera viewpoints
- **Impostor Probes:** 2,244 queries from 500 unenrolled identities

| Metric | Before Update (Baseline) | After Update (Market-1501 Trained) | Improvement |
| :--- | :---: | :---: | :---: |
| **Open-Set ROC AUC** | 0.6718 | **0.9635** | **+29.17 pp (+43.4%)** |
| **Equal Error Rate (EER)** | 37.07% | **8.82%** | **-28.25 pp (76.2% cut)** |
| **FAR @ Recall = 90%** | 95.63% | **6.46%** | **-89.17 pp (93.2% cut)** |
| **Target ~20% FAR Point** | FAR 20.05% / TAR 54.18% | **FAR 20.23% / TAR 94.48%** | **+40.30 pp Genuine TAR** |
| **TAR @ FAR Budget = 1%** | 32.74% | **81.94%** | **+49.20 pp (+150.3%)** |
| **Closed-Set Rank-1** | 70.46% | **98.58%** | **+28.12 pp (+39.9%)** |
| **Mean Average Precision (mAP)** | 10.79% | **63.80%** | **+53.01 pp (+491.2%)** |

---

## System Capabilities & Operational Modes

### 1. Interactive Visual Presentations & Live Dashboards
- **Executive Presentation Deck (`presentation.html`):** 12 interactive slides designed for stakeholder presentations, featuring full-screen mode, keyboard navigation, speaker notes, and architectural diagrams.
- **Analytics Dashboard (`dashboard.html`):** Offline-first analytics platform featuring dynamic threshold and margin simulators, before-and-after comparison matrices, and live probe simulation.

### 2. Live Surveillance Camera Integration
- **Real-Time Stream Processing (`realtime_camera_reid.py`):** Ingests live USB webcams, RTSP network IP cameras, and CCTV video recordings.
- **Access Gate Framing:** Automatically crops 2:1 aspect ratio pedestrian regions, runs ONNX feature extraction, applies the 3-gate rejection boundary, and renders live HUD bounding boxes with identity tags.

### 3. Open-Set Benchmark & Quantitative Verification
- **Automated Protocol Evaluator (`benchmark_market_openset.py`):** Measures ROC AUC, Equal Error Rate, False Accept Rates at fixed recall targets, and Rank-1 retrieval on real-world Market-1501 multi-camera surveillance data.
- **Fast Verification Module (`demo_inference.py`):** Rapid verification test of the 3-gate open-set rejection cascade.


---

## Repository Structure

```
d:/zed digital/
├── presentation.html                     # 12-slide interactive executive presentation
├── dashboard.html                        # Interactive analytics dashboard with Market-1501 tabs
├── PRESENTATION_AND_DEFENSE_GUIDE.md     # Comprehensive defense script, elevator pitch, 20 Q&As
├── realtime_camera_reid.py               # Live camera / RTSP stream runner with Access Gate HUD
├── benchmark_market_openset.py           # Automated Market-1501 open-set evaluation benchmark
├── train_market1501.py                   # PyTorch GPU metric learning trainer (RTX 2050 AMP)
├── generate_market_comparison_plots.py   # Publication-grade comparative figure generator
├── demo_inference.py                     # Rapid synthetic open-set verification demo
├── openset_reid/                         # Core Python package
│   ├── models/                           # OmniScale backbone, Dual-Granularity, Sub-Center ArcFace
│   ├── open_set/                         # 3-Gate cascade, contrast margin, EVT Weibull modeling
│   ├── deployment/                       # ONNX export, runtime inference, latency profilers
│   ├── evaluation/                       # Open-set metrics (ROC, DET, FAR@Recall, TAR@FAR)
│   └── cpp/                              # High-performance C++ matching engine (0.28ms / 1k IDs)
├── data/
│   ├── sample_cctv.mp4                   # Sample CCTV video for camera stream demonstration
│   └── low_variance_benchmark/           # Curated uniform benchmark dataset
└── experiments/
    ├── market1501_updated/               # GPU-trained checkpoint (openset_reid_checkpoint.pth)
    ├── deployment/                       # Optimized ONNX model graphs (openset_reid.onnx)
    └── reports/                          # Benchmark JSON reports and publication figures
```
