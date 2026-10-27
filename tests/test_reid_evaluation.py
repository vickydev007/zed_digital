import pytest
import numpy as np
from openset_reid.open_set.decision_boundary import OpenSetDecisionEngine, MatchDecision
from openset_reid.open_set.calibrator import OpenSetMatcher


class TestOpenSetDecisionEngine:
    def test_empty_gallery_handling(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        decision = engine.evaluate_match(gallery_ids=[], scores=np.array([]), calibrated_confidence=0.0)
        assert decision.is_accepted is False
        assert decision.matched_identity is None
        assert decision.rejection_reason == "Empty gallery"
        assert decision.raw_score == 0.0
        assert decision.contrast_margin == 0.0

    def test_threshold_boundary_exact_match(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.70, 0.60])
        gallery_ids = ["worker_1", "worker_2"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.85)
        assert decision.is_accepted is True
        assert decision.matched_identity == "worker_1"
        assert decision.contrast_margin == pytest.approx(0.10)
        assert decision.rejection_reason is None

    def test_threshold_boundary_just_below(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.6999, 0.60])
        gallery_ids = ["worker_1", "worker_2"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.80)
        assert decision.is_accepted is False
        assert decision.matched_identity is None
        assert "Score below threshold" in decision.rejection_reason

    def test_margin_boundary_exact_match(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.80, 0.75])
        gallery_ids = ["worker_A", "worker_B"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.9)
        assert decision.is_accepted is True
        assert decision.matched_identity == "worker_A"
        assert decision.contrast_margin == pytest.approx(0.05)

    def test_margin_boundary_insufficient(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.92, 0.90])
        gallery_ids = ["worker_A", "worker_B"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.95)
        assert decision.is_accepted is False
        assert decision.matched_identity is None
        assert "Ambiguous uniform match / insufficient margin" in decision.rejection_reason
        assert decision.contrast_margin == pytest.approx(0.02)

    def test_single_identity_gallery(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.85])
        gallery_ids = ["solo_worker"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.9)
        assert decision.is_accepted is True
        assert decision.matched_identity == "solo_worker"
        assert decision.second_identity is None
        assert decision.contrast_margin == pytest.approx(0.85)

    def test_multiple_crops_same_identity_ranking(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.95, 0.93, 0.80])
        gallery_ids = ["worker_X", "worker_X", "worker_Y"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.99)
        assert decision.is_accepted is True
        assert decision.matched_identity == "worker_X"
        assert decision.second_identity == "worker_Y"
        assert decision.contrast_margin == pytest.approx(0.95 - 0.80)

    def test_exact_tie_handling(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.05)
        scores = np.array([0.90, 0.90])
        gallery_ids = ["worker_1", "worker_2"]
        decision = engine.evaluate_match(gallery_ids=gallery_ids, scores=scores, calibrated_confidence=0.90)
        assert decision.is_accepted is False
        assert decision.contrast_margin == pytest.approx(0.0)
        assert "Ambiguous uniform match" in decision.rejection_reason


class TestOpenSetMatcherIntegration:
    def test_matcher_enroll_and_match(self):
        matcher = OpenSetMatcher(score_threshold=0.70, contrast_margin=0.05, use_cohort=False, use_evt=False)
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        matcher.enroll("alice", v1)
        matcher.enroll("bob", v2)

        q_alice = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        dec = matcher.match(q_alice)
        assert dec.is_accepted is True
        assert dec.matched_identity == "alice"
        assert dec.raw_score == pytest.approx(1.0)
        assert dec.second_identity == "bob"
        assert dec.contrast_margin == pytest.approx(1.0)

        q_bob = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        dec_bob = matcher.match(q_bob)
        assert dec_bob.is_accepted is True
        assert dec_bob.matched_identity == "bob"

        q_unknown = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        dec_unk = matcher.match(q_unknown)
        assert dec_unk.is_accepted is False
        assert dec_unk.raw_score == pytest.approx(0.0)
        assert "Score below threshold" in dec_unk.rejection_reason

    def test_unnormalized_query_handling(self):
        matcher = OpenSetMatcher(score_threshold=0.70, contrast_margin=0.05, use_cohort=False, use_evt=False)
        v1 = np.array([5.0, 0.0], dtype=np.float32)
        matcher.enroll("alice", v1)

        q = np.array([10.0, 0.0], dtype=np.float32)
        dec = matcher.match(q)
        assert dec.is_accepted is True
        assert dec.matched_identity == "alice"
        assert dec.raw_score == pytest.approx(1.0, abs=1e-5)

    def test_nan_and_zero_vector_safety(self):
        matcher = OpenSetMatcher(score_threshold=0.70, contrast_margin=0.05, use_cohort=False, use_evt=False)
        v1 = np.array([1.0, 0.0], dtype=np.float32)
        matcher.enroll("alice", v1)

        zero_q = np.array([0.0, 0.0], dtype=np.float32)
        dec = matcher.match(zero_q)
        assert dec.raw_score == pytest.approx(0.0, abs=1e-4)


class TestMetricAggregationEdgeCases:
    def test_zero_denominator_safeguards(self):
        total_gen = 0
        total_imp = 0
        correct_accepts = 0
        correct_rejections = 0

        tar = (correct_accepts / total_gen) if total_gen > 0 else 0.0
        far = (0 / total_imp) if total_imp > 0 else 0.0
        trr = (correct_rejections / total_imp) if total_imp > 0 else 0.0

        assert tar == 0.0
        assert far == 0.0
        assert trr == 0.0
