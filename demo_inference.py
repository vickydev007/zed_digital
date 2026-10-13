"""
Quick Demo: Shows open-set matching in action with synthetic embeddings.
Demonstrates the full pipeline without needing a trained model checkpoint.
"""
import sys
sys.path.insert(0, "d:/zed digital")

import numpy as np
import torch
from openset_reid.models.openset_model import create_openset_model
from openset_reid.open_set.calibrator import OpenSetMatcher, ConfidenceCalibrator
from openset_reid.open_set.evt_calibration import EVTTailCalibrator

print("=" * 70)
print("OPEN-SET RE-ID DEMO  —  Security Uniform Scenario")
print("=" * 70)

# ── Setup model ──────────────────────────────────────────────────────────────
model = create_openset_model(dual_granularity=True, embedding_dim=512)
model.eval()
print(f"\nModel: {sum(p.numel() for p in model.parameters())/1e6:.2f}M parameters")

# ── Simulate enrolled gallery of 5 security officers ─────────────────────────
rng = np.random.RandomState(0)
D = 512

# Each enrolled person has a "true" embedding (simulating trained model output)
enrolled_embeddings = {}
enrolled_names = ["Officer Alice", "Officer Bob", "Officer Charlie",
                  "Officer Diana", "Officer Eve"]
for name in enrolled_names:
    emb = rng.randn(D).astype(np.float32)
    emb /= np.linalg.norm(emb)
    enrolled_embeddings[name] = emb

# Setup matcher
matcher = OpenSetMatcher(
    score_threshold=0.45,   # Lowered for untrained embedding demo (trained model: 0.65)
    margin_threshold=0.05,
    evt_threshold=0.35,
    use_cohort=False,
    use_evt=True
)

# Enroll gallery
for name, emb in enrolled_embeddings.items():
    matcher.enroll(name, emb)

# Fit EVT on realistic impostor distances (random embeddings are ~sqrt(2) apart)
imp_dists = np.clip(rng.normal(1.35, 0.12, 500), 0.6, 1.9)
matcher.fit_evt_from_distances(imp_dists)

print(f"\nGallery enrolled: {len(enrolled_names)} officers")
print("\n" + "─" * 70)

# ── Test Scenarios ────────────────────────────────────────────────────────────
def query(name: str, query_emb: np.ndarray, label: str):
    dec = matcher.match(query_emb)
    status = "ACCEPT" if dec.is_accepted else "REJECT"
    sym    = "[+]" if dec.is_accepted else "[-]"
    print(f"\n  {sym} {label}")
    print(f"     Query identity:  {name}")
    print(f"     Decision:        {status}")
    if dec.is_accepted:
        print(f"     Matched to:      {dec.matched_identity}")
    else:
        print(f"     Rejection:       {dec.rejection_reason}")
    print(f"     Top score:       {dec.raw_score:.4f} | Margin: {dec.contrast_margin:.4f} | "
          f"Confidence: {dec.confidence:.4f} | EVT: {dec.evt_tail_score:.4f}")
    return dec

# Scenario 1: Genuine probe — Alice comes back to camera
print("\n[SCENARIO 1] Genuine Enrolled Probes")
alice_probe = enrolled_embeddings["Officer Alice"] + rng.randn(D).astype(np.float32) * 0.08
alice_probe /= np.linalg.norm(alice_probe)
query("Officer Alice", alice_probe, "Alice returning to camera (close match)")

bob_probe = enrolled_embeddings["Officer Bob"] + rng.randn(D).astype(np.float32) * 0.12
bob_probe /= np.linalg.norm(bob_probe)
query("Officer Bob", bob_probe, "Bob from different camera angle")

# Scenario 2: Unknown impostor in same navy uniform
print("\n[SCENARIO 2] Unknown Impostors (same navy uniform)")
for i, impostor_name in enumerate(["Unknown_Guard_07", "Unknown_Guard_12"]):
    impostor_emb = rng.randn(D).astype(np.float32)
    impostor_emb /= np.linalg.norm(impostor_emb)
    query(impostor_name, impostor_emb, f"Unenrolled guard in same uniform (impostor {i+1})")

# Scenario 3: Ambiguous / near-twin case — very similar to Charlie but not quite
print("\n[SCENARIO 3] Ambiguous Near-Twin (uniform similarity)")
# Person who looks almost identical to Charlie AND Diana simultaneously
charlie = enrolled_embeddings["Officer Charlie"]
diana   = enrolled_embeddings["Officer Diana"]
near_twin = 0.48 * charlie + 0.48 * diana + 0.04 * rng.randn(D).astype(np.float32)
near_twin /= np.linalg.norm(near_twin)
query("UNKNOWN (similar to Charlie+Diana)", near_twin,
      "Near-twin impostor (ambiguous same-uniform match)")

print("\n" + "─" * 70)
print("\nGallery summary:")
print(f"  Enrolled: {matcher.gallery_matrix.shape[0]} officers")
print(f"  Embedding dimension: {matcher.gallery_matrix.shape[1]}-d")
print("\nDemo complete.")
