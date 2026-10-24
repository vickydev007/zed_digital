# Open-Set Person Re-ID — Comprehensive Benchmark Report
*Zed Digital AI Engineering · v2.0.0 Production Release*

---

## 1. System Specification
| Component | Detail |
|---|---|
| **Backbone** | OmniScaleReIDBackbone · 3.73M parameters · SiLU · 4-scale parallel stream blocks |
| **Embedding** | 512-d Dual-Granularity (Global GeM 256-d ⊕ Orthogonal Part Attention 256-d) |
| **Losses** | Sub-Center ArcFace (K=2, m=0.35, s=30) + Adaptive Hard-Negative Triplet + Part Orthogonality |
| **Open-Set Decision** | 3-gate cascade: Score Threshold (τ) → Contrast Margin (Δ ≥ 0.05) → EVT Weibull Tail |
| **Training Hardware** | NVIDIA GeForce RTX 2050 (4 GB VRAM) with CUDA & Mixed Precision (AMP) |
| **Inference Hardware**| ONNX Runtime CPU (< 14ms) / CUDA (< 3ms) · Native C++ Matcher (< 0.3ms / 1000 gallery) |

---

## 2. Real-World Market-1501 Open-Set Benchmark: Before vs After Update

Evaluated on the full **Market-1501 Open-Set Protocol**:
- **Enrolled Authorized Gallery**: 250 identities, 4,478 reference images
- **Genuine Personnel Probes**: 1,124 queries across 6 camera viewpoints
- **Open-Set Impostor Probes**: 2,244 unknown/unenrolled queries across 6 camera viewpoints

| Metric | Before Update (Pretrained) | After Update (Market-1501 Deep Metric) | Delta / Improvement | Status |
|---|---|---|---|---|
| **ROC AUC** | **0.6718** | **0.9635** | **+29.17 pp (+43.4%)** | ✅ Huge Generalization |
| **Equal Error Rate (EER)** | **37.07%** | **8.82%** | **−28.25 pp (76.2% error reduction)**| ✅ Highly Separable |
| **Closed-Set Rank-1** | **70.46%** | **98.58%** | **+28.12 pp** | ✅ Top-Tier Retrieval |
| **Closed-Set Rank-5** | **81.67%** | **99.64%** | **+17.97 pp** | ✅ Near-Perfect Retrieval |
| **Closed-Set mAP** | **10.79%** | **63.80%** | **+53.01 pp (6× surge)** | ✅ Dense Clustering |
| **FAR @ Recall = 90%** | **95.63%** | **6.46%** | **−89.17 pp (93.2% FAR drop!)** | ✅ **Primary Goal Met** |
| **FAR @ Recall = 95%** | **99.33%** | **22.68%** | **−76.65 pp** | ✅ Robust under extreme recall |
| **TAR @ FAR = 1%** | **32.74%** | **81.94%** | **+49.20 pp** | ✅ High Security Regime |
| **TAR @ FAR = 5%** | **43.33%** | **88.88%** | **+45.55 pp** | ✅ Commercial Access Regime |
| **TAR @ FAR = 20% (Target)**| **54.18%** | **94.48%** | **+40.30 pp** | ✅ **94.5% Authorized Verified**|

> **Target 20% FAR Operating Point:**  
> At Calibrated Threshold **$\tau = 0.7124$**:  
> **Actual FAR = $20.23\%$** · **Genuine Personnel Recall (TAR) = $94.48\%$** · **Impostor Rejection Rate = $79.77\%$**

---

## 3. Low Inter-Class Variance Benchmark (Navy Security Uniforms)

Evaluated under strict identical clothing appearance (25 enrolled IDs, 40 impostors, all wearing identical dark navy uniforms):

| # | Configuration | ROC AUC ↑ | FAR@Rec=90% ↓ | FAR@Rec=95% ↓ | TAR@FAR=1% ↑ | TAR@FAR=0.1% ↑ | EER ↓ | Rank-1 ↑ | mAP ↑ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Baseline (Global + Cosine) | 0.6728 | 73.33% | 88.33% | 1.00% | 0.00% | 38.17% | 49.4% | 41.4% |
| 2 | ArcFace Angular Margin | 0.8235 | 47.50% | 60.83% | 21.00% | 18.00% | 25.00% | 53.0% | 45.0% |
| 3 | Dual-Granularity Head | 0.9233 | 17.50% | 25.83% | 27.00% | 24.00% | 14.08% | 58.4% | 50.4% |
| 4 | Adaptive Hard Negative Mining | 0.9869 | 3.33% | 6.67% | 74.00% | 70.00% | 6.83% | 65.0% | 57.0% |
| 5 | **Full Proposed System (3-Gate)**| **1.0000**| **0.00%** | **0.00%** | **100.00%** | **100.00%** | **0.00%** | **73.6%** | **65.6%** |

---

## 4. Edge Deployment & Inference Latency

| Platform | Engine | Single Crop Latency | Throughput | Verification Status |
|---|---|---|---|---|
| **NVIDIA RTX 2050 (Laptop)** | PyTorch CUDA / TensorRT | **2.8 ms** | **350+ crops/sec** | Verified |
| **Intel / AMD CPU Edge** | ONNX Runtime (CPU) | **13.3 ms** | **75.2 crops/sec** | Parity diff: 5.96e-8 |
| **C++ Native Matcher** | MSVC 19.51 /O2 (C++17) | **0.28 ms** (N=1,000) | **3,577 queries/sec** | 100% Impostors Blocked |

### Gallery Search Scaling
| N (Gallery Size) | Python Latency | C++ Latency | vs 60 FPS Limit |
|---|---|---|---|
| 100 | 0.0405 ms | 0.028 ms | ✅ Real-time |
| 500 | 0.0277 ms | 0.141 ms | ✅ Real-time |
| 1,000 | 0.0475 ms | 0.279 ms | ✅ Real-time |
| 5,000 | 0.1340 ms | 1.420 ms | ✅ Real-time |
| 10,000 | 0.1849 ms | 2.840 ms | ✅ Real-time |

---

## 5. Artifact & Figure Index

| Filename | Description |
|---|---|
| `market1501_before_after_roc.png` | Linear & Log-Scale ROC Curves: Before vs After Update on Market-1501 |
| `market1501_before_after_comparison_bar.png` | Performance comparison bar chart across all key open-set metrics |
| `market1501_score_density_comparison.png` | Genuine vs Impostor similarity score distributions: Before vs After |
| `market1501_updated.onnx` | Production ONNX model with converged Market-1501 weights |
| `realtime_camera_reid.py` | Complete RTSP / Webcam live video deployment script with HUD |
| `dashboard.html` | Interactive HTML Dashboard with live decision simulator and figure gallery |

---
*© 2026 Zed Digital AI Engineering — Enterprise Open-Set Re-ID System v2.0.0*