"""
Publication-Grade ROC, DET, Score Distribution and Part-Attention Visualisation Suite.
Generates all figures needed for reporting and ablation analysis.
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from typing import Dict, List, Optional, Tuple


# ── Style Constants ────────────────────────────────────────────────────────────
PALETTE = [
    "#E84545",  # red      – Baseline
    "#F5A623",  # orange   – + ArcFace
    "#4ECDC4",  # teal     – + Dual Granularity
    "#2E86AB",  # blue     – + Adaptive Mining
    "#44CF6C",  # green    – Full Proposed System
]
MARKERS = ["o", "s", "^", "D", "*"]
LEGEND_FONT = 9
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.4,
    "grid.linestyle": "--",
})


def plot_roc_det_comparison(experiments: Dict[str, Dict], out_path: str):
    """
    3-panel figure:
    Left  – Linear ROC (TAR vs FAR)
    Centre – Log-scale ROC (operational low-FAR regime)
    Right  – DET curve (FRR vs FAR, both log scale)
    """
    fig = plt.figure(figsize=(19, 6), dpi=150)
    gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35)
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]

    exp_names = list(experiments.keys())

    for i, (name, res) in enumerate(experiments.items()):
        far = np.array(res["far_curve"])
        tar = np.array(res["tar_curve"])
        auc = res["roc_auc"]
        eer = res["eer"]
        c = PALETTE[i % len(PALETTE)]
        lbl = f"{name[:32]}…" if len(name) > 32 else name

        # Panel 1: Linear ROC
        axes[0].plot(far, tar, color=c, lw=2.0,
                     label=f"{lbl} (AUC={auc:.4f})")
        axes[0].scatter([eer], [1.0 - eer], color=c, s=60, zorder=5, marker=MARKERS[i % 5])

        # Panel 2: Log-scale ROC
        valid = far > 0
        axes[1].semilogx(far[valid], tar[valid], color=c, lw=2.0, label=lbl)

        # Panel 3: DET (FRR vs FAR, both log)
        frr = 1.0 - tar
        valid_det = (far > 1e-4) & (frr > 1e-4)
        axes[2].loglog(far[valid_det], frr[valid_det], color=c, lw=2.0, label=lbl)

    # Panel 1 formatting
    axes[0].plot([0, 1], [0, 1], "k--", lw=1, alpha=0.4, label="Random Guess")
    axes[0].set(xlabel="False Accept Rate (FAR)", ylabel="True Accept Rate (TAR/Recall)",
                title="ROC Curve — Ablation Comparison",
                xlim=[0, 1], ylim=[0, 1.02])
    axes[0].legend(loc="lower right", fontsize=LEGEND_FONT, framealpha=0.9)

    # Panel 2 formatting
    axes[1].set(xlabel="FAR (Log Scale)", ylabel="TAR",
                title="Operational Low-FAR Regime",
                xlim=[1e-3, 1.0], ylim=[0.0, 1.02])
    axes[1].legend(loc="lower right", fontsize=LEGEND_FONT, framealpha=0.9)

    # Panel 3 formatting
    axes[2].plot([1e-3, 1.0], [1e-3, 1.0], "k--", lw=1, alpha=0.4)
    axes[2].set(xlabel="FAR (Log Scale)", ylabel="FRR (Log Scale)",
                title="Detection Error Tradeoff (DET)",
                xlim=[1e-3, 1.0], ylim=[1e-3, 1.0])
    axes[2].legend(loc="upper right", fontsize=LEGEND_FONT, framealpha=0.9)

    fig.suptitle("Open-Set Re-ID under Low Inter-Class Variance  ·  Full Ablation Study",
                 fontsize=13, fontweight="bold", y=1.01)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")


def plot_score_distributions(genuine_scores: np.ndarray,
                             impostor_scores: np.ndarray,
                             out_path: str,
                             title: str = "Score Distributions (Genuine vs Impostor)"):
    """
    Overlapping KDE plots of genuine vs impostor score distributions.
    Shows the separability challenge under same-uniform conditions.
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=150)

    # KDE plot
    ax = axes[0]
    ax.set_title(title, fontweight="bold")
    sns.kdeplot(genuine_scores, ax=ax, fill=True, alpha=0.45,
                color=PALETTE[4], label=f"Genuine (N={len(genuine_scores)})")
    sns.kdeplot(impostor_scores, ax=ax, fill=True, alpha=0.45,
                color=PALETTE[0], label=f"Impostor (N={len(impostor_scores)})")
    ax.axvline(np.mean(genuine_scores), color=PALETTE[4], ls="--", lw=1.5)
    ax.axvline(np.mean(impostor_scores), color=PALETTE[0], ls="--", lw=1.5)
    ax.set(xlabel="Similarity Score", ylabel="Density")
    ax.legend(fontsize=LEGEND_FONT)

    # Box plot comparing distributions
    ax2 = axes[1]
    ax2.set_title("Score Box Plots", fontweight="bold")
    bp = ax2.boxplot([genuine_scores, impostor_scores],
                     labels=["Genuine", "Impostor"],
                     patch_artist=True, notch=True,
                     medianprops={"color": "black", "lw": 2})
    bp["boxes"][0].set_facecolor(PALETTE[4])
    bp["boxes"][0].set_alpha(0.7)
    bp["boxes"][1].set_facecolor(PALETTE[0])
    bp["boxes"][1].set_alpha(0.7)
    ax2.set(ylabel="Similarity Score")

    overlap = _compute_score_overlap(genuine_scores, impostor_scores)
    fig.text(0.5, -0.02,
             f"Score Overlap Index: {overlap:.3f}  |  "
             f"Genuine mean: {genuine_scores.mean():.3f}  |  "
             f"Impostor mean: {impostor_scores.mean():.3f}",
             ha="center", fontsize=9, style="italic")

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")


def _compute_score_overlap(a: np.ndarray, b: np.ndarray,
                           n_bins: int = 200) -> float:
    """Bhattacharyya coefficient as overlap measure."""
    lo = min(a.min(), b.min())
    hi = max(a.max(), b.max())
    bins = np.linspace(lo, hi, n_bins + 1)
    ha = np.histogram(a, bins=bins, density=True)[0]
    hb = np.histogram(b, bins=bins, density=True)[0]
    bin_w = bins[1] - bins[0]
    return float(np.sum(np.sqrt(ha * hb)) * bin_w)


def plot_ablation_metrics_table(summary: List[Dict], out_path: str):
    """
    Renders a heatmap-style table of ablation metrics across all configurations.
    """
    methods = [d["Method"] for d in summary]
    metric_keys = ["AUC", "FAR @ Rec=90%", "FAR @ Rec=95%", "TAR @ FAR=1%", "EER", "Rank-1", "mAP"]
    metric_labels = ["ROC AUC", "FAR@Rec=90%", "FAR@Rec=95%", "TAR@FAR=1%", "EER", "Rank-1", "mAP"]

    # Parse numeric values
    data = []
    for row in summary:
        r = []
        for k in metric_keys:
            val_str = row.get(k, "0.00%")
            r.append(float(val_str.replace("%", "")))
        data.append(r)
    data = np.array(data)

    # Normalise each column for colour mapping (0=worst, 1=best)
    # For AUC, TAR@FAR=1%, Rank-1, mAP -> higher is better
    # For FAR@Rec=90%, FAR@Rec=95%, EER -> lower is better
    higher_better = [True, False, False, True, False, True, True]
    normed = np.zeros_like(data)
    for j, hb in enumerate(higher_better):
        col = data[:, j]
        col_min, col_max = col.min(), col.max()
        if col_max > col_min:
            normed[:, j] = (col - col_min) / (col_max - col_min)
            if not hb:
                normed[:, j] = 1.0 - normed[:, j]
        else:
            normed[:, j] = 1.0

    fig, ax = plt.subplots(figsize=(14, max(4, len(methods) * 0.8 + 2)), dpi=150)
    im = ax.imshow(normed, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels([f"{i+1}. {m}" for i, m in enumerate(methods)], fontsize=9)

    for i in range(len(methods)):
        for j in range(len(metric_keys)):
            ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center",
                    fontsize=8, color="black", fontweight="bold")

    ax.set_title("Ablation Study — Open-Set Re-ID Metrics\n(Green = Best, Red = Worst per column)",
                 fontsize=11, fontweight="bold", pad=15)
    plt.colorbar(im, ax=ax, shrink=0.6, label="Relative Performance")
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")


def plot_gallery_latency_scaling(gallery_scaling: Dict[int, float], out_path: str):
    """
    Plots gallery search latency as a function of gallery size (N).
    """
    sizes = sorted(gallery_scaling.keys())
    times = [gallery_scaling[s] for s in sizes]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    ax.plot(sizes, times, color=PALETTE[2], lw=2.5, marker="o", ms=8, zorder=3)
    ax.fill_between(sizes, times, alpha=0.15, color=PALETTE[2])

    # Annotate each point
    for s, t in zip(sizes, times):
        ax.annotate(f"{t:.3f}ms", (s, t), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=8)

    ax.set(xlabel="Gallery Size (N enrolled identities)",
           ylabel="Matching Latency per Query (ms)",
           title="Gallery Search Scalability\nEuclidean NN Search (512-d embeddings)",
           xscale="log", xlim=[min(sizes) * 0.8, max(sizes) * 1.2])
    ax.set_xticks(sizes)
    ax.set_xticklabels([str(s) for s in sizes])
    ax.axhline(1.0 / 60.0 * 1000, color="red", ls="--", lw=1.5, alpha=0.6,
               label="60 FPS deadline (16.7ms)")
    ax.legend()

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out_path}")
