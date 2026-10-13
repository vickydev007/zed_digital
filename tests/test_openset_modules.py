"""
Unit Tests: Open-Set Matcher, EVT Calibration, Cohort Normalization, Decision Boundary.
"""
import sys
sys.path.insert(0, "d:/zed digital")

import numpy as np
from openset_reid.open_set.evt_calibration import EVTTailCalibrator
from openset_reid.open_set.cohort_calibration import CohortCalibrator
from openset_reid.open_set.decision_boundary import OpenSetDecisionEngine
from openset_reid.open_set.calibrator import OpenSetMatcher, ConfidenceCalibrator
from openset_reid.evaluation.metrics import OpenSetEvaluationMetrics

print("=" * 60)
print("OPEN-SET MODULE UNIT TESTS")
print("=" * 60)

rng = np.random.RandomState(42)

# ── 1. EVT Calibrator ────────────────────────────────────────
print("\n[1] EVTTailCalibrator")
evt = EVTTailCalibrator(tail_size=20)
# Realistic impostor distances: unit vectors in high-dim space cluster around sqrt(2) ~ 1.41
# Impostors: d ~ N(1.35, 0.12), clipped to [0.6, 1.9]
imp_dists = np.clip(rng.normal(1.35, 0.12, 300), 0.6, 1.9).astype(np.float64)
fitted = evt.fit_tail(imp_dists)
assert fitted, "EVT fit should succeed"
print(f"  Weibull params: {evt.weibull_params}")
# Genuine close match: dist=0.25 -> score should be HIGH (fewer impostors this close)
score_close = evt.compute_evt_score(0.25)
# Far impostor match: dist=1.30 -> score LOW (impostors routinely this far)
score_far = evt.compute_evt_score(1.30)
print(f"  EVT score (dist=0.25, genuine-like):   {score_close:.4f}")
print(f"  EVT score (dist=1.30, impostor-like):  {score_far:.4f}")
assert score_close > score_far, \
    f"EVT score should be higher for close match ({score_close:.4f} vs {score_far:.4f})"
print("  PASSED OK")


# ── 2. Cohort Calibrator ─────────────────────────────────────
print("\n[2] CohortCalibrator (Z-Normalization)")
cohort_embs = rng.randn(50, 256).astype(np.float32)
norms = np.linalg.norm(cohort_embs, axis=1, keepdims=True)
cohort_embs /= norms
cal = CohortCalibrator(cohort_embs)
assert cal.is_ready()
q_emb = rng.randn(256).astype(np.float32)
q_emb /= np.linalg.norm(q_emb)
mu, sigma = cal.compute_probe_stats(q_emb)
raw_sims = np.dot(cohort_embs[:10], q_emb)
z_scores = cal.normalize_scores(q_emb, raw_sims)
print(f"  Cohort mu={mu:.4f}, sigma={sigma:.4f}")
print(f"  Z-score range: [{z_scores.min():.3f}, {z_scores.max():.3f}]")
assert sigma > 0, "Sigma should be positive"
print("  PASSED OK")

# ── 3. Confidence Calibrator ─────────────────────────────────
print("\n[3] ConfidenceCalibrator (Platt Scaling)")
conf_cal = ConfidenceCalibrator(method="platt")
# Simulate: genuine pairs ~ N(0.75, 0.05), impostor ~ N(0.55, 0.08)
genuine_s = rng.normal(0.75, 0.05, 200).clip(0, 1)
impostor_s = rng.normal(0.55, 0.08, 300).clip(0, 1)
all_scores = np.concatenate([genuine_s, impostor_s])
all_labels = np.concatenate([np.ones(200), np.zeros(300)])
conf_cal.fit(all_scores, all_labels)
p_genuine = conf_cal.predict_probability(0.80)
p_impostor = conf_cal.predict_probability(0.45)
print(f"  P(genuine | score=0.80): {p_genuine:.4f}")
print(f"  P(genuine | score=0.45): {p_impostor:.4f}")
assert p_genuine > 0.5, f"Score 0.80 should be classified as genuine (got {p_genuine:.4f})"
assert p_impostor < 0.5, f"Score 0.45 should be rejected (got {p_impostor:.4f})"
print("  PASSED OK")

# ── 4. Decision Engine ───────────────────────────────────────
print("\n[4] OpenSetDecisionEngine")
engine = OpenSetDecisionEngine(
    score_threshold=0.60,
    margin_threshold=0.05,
    evt_threshold=0.40,
    use_contrast_margin=True,
    use_evt=True
)
# Case A: Clear genuine match - high score, clear margin, EVT OK
scores_a = np.array([0.80, 0.60, 0.55])
dec_a = engine.evaluate_match(["ID1", "ID2", "ID3"], scores_a,
                               calibrated_confidence=0.92, evt_tail_score=0.85)
assert dec_a.is_accepted and dec_a.matched_identity == "ID1", f"Should accept ID1, got: {dec_a}"
print(f"  Case A (Clear genuine): accepted={dec_a.is_accepted}, id={dec_a.matched_identity}  OK")

# Case B: Ambiguous uniform match - top two very close (same uniform)
scores_b = np.array([0.78, 0.76, 0.50])
dec_b = engine.evaluate_match(["PersonA", "PersonB", "PersonC"], scores_b,
                               calibrated_confidence=0.78, evt_tail_score=0.82)
assert not dec_b.is_accepted, f"Should reject ambiguous match, got accepted={dec_b.is_accepted}"
print(f"  Case B (Ambiguous):     accepted={dec_b.is_accepted}, reason={dec_b.rejection_reason}  OK")

# Case C: Score below threshold (total stranger)
scores_c = np.array([0.45, 0.40, 0.35])
dec_c = engine.evaluate_match(["PersonX", "PersonY", "PersonZ"], scores_c,
                               calibrated_confidence=0.10, evt_tail_score=0.95)
assert not dec_c.is_accepted, "Score too low should be rejected"
print(f"  Case C (Below thresh):  accepted={dec_c.is_accepted}, reason={dec_c.rejection_reason}  OK")

# ── 5. Full OpenSetMatcher (end-to-end) ──────────────────────
print("\n[5] OpenSetMatcher (end-to-end enrollment + matching)")
matcher = OpenSetMatcher(score_threshold=0.50, margin_threshold=0.04, evt_threshold=0.30,
                         use_cohort=False, use_evt=False)
# Enroll 5 identities with 256-d embeddings
enrolled_embs = rng.randn(5, 256).astype(np.float32)
enrolled_embs /= np.linalg.norm(enrolled_embs, axis=1, keepdims=True)
matcher.enroll_batch(["alice", "bob", "charlie", "diana", "eve"], enrolled_embs)
assert matcher.gallery_matrix.shape == (5, 256)

# Query with a known enrolled probe (near alice)
alice_query = enrolled_embs[0] + rng.randn(256).astype(np.float32) * 0.05
alice_query /= np.linalg.norm(alice_query)
result = matcher.match(alice_query)
print(f"  Query (near alice): accepted={result.is_accepted}, "
      f"matched_to={result.matched_identity}, score={result.raw_score:.4f}")
assert result.matched_identity == "alice", \
    f"Should match alice, got {result.matched_identity} (score={result.raw_score:.4f})"
print("  PASSED OK")

# ── 6. Evaluation Metrics ────────────────────────────────────
print("\n[6] OpenSetEvaluationMetrics")
# Simulate score distributions
gen_scores = rng.normal(0.78, 0.06, 150).clip(0, 1).astype(np.float32)
imp_scores = rng.normal(0.52, 0.09, 250).clip(0, 1).astype(np.float32)
far, tar, thresholds, roc_auc = OpenSetEvaluationMetrics.compute_roc_curve(gen_scores, imp_scores)
far_at_r = OpenSetEvaluationMetrics.compute_far_at_fixed_recall(far, tar, [0.85, 0.90, 0.95])
tar_at_f = OpenSetEvaluationMetrics.compute_tar_at_fixed_far(far, tar, [0.001, 0.01, 0.05])
eer, _ = OpenSetEvaluationMetrics.compute_equal_error_rate(far, tar)
print(f"  ROC AUC:         {roc_auc:.4f}")
print(f"  EER:             {eer*100:.2f}%")
print(f"  FAR@Rec=90%:     {far_at_r[0.90]*100:.2f}%")
print(f"  FAR@Rec=95%:     {far_at_r[0.95]*100:.2f}%")
print(f"  TAR@FAR=1%:      {tar_at_f[0.01]*100:.2f}%")
print(f"  TAR@FAR=0.1%:    {tar_at_f[0.001]*100:.2f}%")
assert roc_auc > 0.7, f"Simulated AUC too low: {roc_auc}"
print("  PASSED OK")

print("\n" + "=" * 60)
print("ALL OPEN-SET MODULE TESTS PASSED")
print("=" * 60)
