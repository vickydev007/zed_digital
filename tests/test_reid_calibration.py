import pytest
import numpy as np
from openset_reid.evaluation.metrics import wilson_score_interval
from openset_reid.open_set.decision_boundary import OpenSetDecisionEngine


class TestCalibrationMath:
    def test_wilson_score_interval_bounds(self):
        lower, upper = wilson_score_interval(10, 10, confidence=0.95)
        assert 0.65 < lower < 1.0
        assert upper == 1.0

        lower, upper = wilson_score_interval(0, 10, confidence=0.95)
        assert lower == 0.0
        assert 0.0 < upper < 0.35

        assert wilson_score_interval(0, 0) == (0.0, 0.0)

    def test_wilson_score_interval_symmetry(self):
        lower, upper = wilson_score_interval(50, 100, confidence=0.95)
        assert lower == pytest.approx(0.4038, abs=1e-3)
        assert upper == pytest.approx(0.5962, abs=1e-3)


class TestCalibratedOperatingPolicies:
    def test_calibrated_frame_policy_acceptance(self):
        engine = OpenSetDecisionEngine(score_threshold=0.70, margin_threshold=0.06)

        scores = np.array([0.72, 0.65])
        ids = ["worker_A", "worker_B"]
        dec = engine.evaluate_match(ids, scores, calibrated_confidence=0.8)
        assert dec.is_accepted is True
        assert dec.matched_identity == "worker_A"
        assert dec.contrast_margin == pytest.approx(0.07)

        scores_near = np.array([0.72, 0.67])
        dec_near = engine.evaluate_match(ids, scores_near, calibrated_confidence=0.8)
        assert dec_near.is_accepted is False
        assert "Ambiguous uniform match" in dec_near.rejection_reason

    def test_calibrated_track_policy_acceptance(self):
        engine = OpenSetDecisionEngine(score_threshold=0.85, margin_threshold=0.10)

        scores = np.array([0.92, 0.77])
        ids = ["worker_A", "worker_B"]
        dec = engine.evaluate_match(ids, scores, calibrated_confidence=0.95)
        assert dec.is_accepted is True
        assert dec.matched_identity == "worker_A"

        scores_imp = np.array([0.82, 0.70])
        dec_imp = engine.evaluate_match(ids, scores_imp, calibrated_confidence=0.80)
        assert dec_imp.is_accepted is False
        assert "Score below threshold" in dec_imp.rejection_reason
