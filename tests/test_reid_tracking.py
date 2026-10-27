import pytest
import numpy as np
from typing import List, Dict, Any, Optional
from openset_reid.open_set.decision_boundary import OpenSetDecisionEngine, MatchDecision


class TrackEvidenceAccumulator:
    """
    Manages track-level embedding aggregation and evidence-weighted identity assignment.
    """
    def __init__(
        self,
        decision_engine: OpenSetDecisionEngine,
        min_observations: int = 3,
        max_history: int = 20,
    ):
        self.engine = decision_engine
        self.min_observations = min_observations
        self.max_history = max_history

        self.embeddings: List[np.ndarray] = []
        self.quality_scores: List[float] = []
        self.confirmed_identity: Optional[str] = None
        self.confirmed_status: str = "UNKNOWN"
        self.last_decision: Optional[MatchDecision] = None

    def add_observation(
        self,
        embedding: np.ndarray,
        quality_score: float,
        gallery_ids: List[str],
        gallery_mat: np.ndarray,
    ) -> MatchDecision:
        emb = embedding.astype(np.float32).ravel()
        emb /= max(np.linalg.norm(emb), 1e-6)

        self.embeddings.append(emb)
        self.quality_scores.append(quality_score)
        if len(self.embeddings) > self.max_history:
            self.embeddings.pop(0)
            self.quality_scores.pop(0)

        n_obs = len(self.embeddings)
        if n_obs < self.min_observations:
            self.last_decision = MatchDecision(
                is_accepted=False,
                matched_identity=None,
                confidence=0.0,
                raw_score=0.0,
                contrast_margin=0.0,
                second_identity=None,
                rejection_reason=f"Insufficient track observations ({n_obs} < {self.min_observations})",
                evt_tail_score=1.0,
            )
            return self.last_decision

        weights = np.array(self.quality_scores, dtype=np.float32)
        weights /= max(np.sum(weights), 1e-6)
        track_emb = np.sum([w * e for w, e in zip(weights, self.embeddings)], axis=0)
        track_emb /= max(np.linalg.norm(track_emb), 1e-6)

        sims = np.dot(gallery_mat, track_emb)
        decision = self.engine.evaluate_match(gallery_ids, sims, calibrated_confidence=0.90)

        if decision.is_accepted:
            self.confirmed_identity = decision.matched_identity
            self.confirmed_status = "OFFICIAL_WORKER"
        else:
            if self.confirmed_identity is not None and n_obs >= self.min_observations + 2:
                pass
            else:
                self.confirmed_identity = None
                self.confirmed_status = "UNKNOWN"

        self.last_decision = decision
        return decision


class TestTrackAwareDecisions:
    @pytest.fixture
    def setup_gallery(self):
        gallery_ids = ["worker_001", "worker_002"]
        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        gallery_mat = np.vstack([v1, v2])
        engine = OpenSetDecisionEngine(score_threshold=0.85, margin_threshold=0.10)
        return gallery_ids, gallery_mat, engine

    def test_insufficient_observations_pending_state(self, setup_gallery):
        gallery_ids, gallery_mat, engine = setup_gallery
        accumulator = TrackEvidenceAccumulator(engine, min_observations=3)

        obs1 = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)
        dec1 = accumulator.add_observation(obs1, 0.8, gallery_ids, gallery_mat)
        assert dec1.is_accepted is False
        assert "Insufficient track observations" in dec1.rejection_reason

        dec2 = accumulator.add_observation(obs1, 0.8, gallery_ids, gallery_mat)
        assert dec2.is_accepted is False
        assert "Insufficient track observations" in dec2.rejection_reason

        dec3 = accumulator.add_observation(obs1, 0.8, gallery_ids, gallery_mat)
        assert dec3.is_accepted is True
        assert dec3.matched_identity == "worker_001"
        assert accumulator.confirmed_status == "OFFICIAL_WORKER"

    def test_outlier_frame_does_not_flip_established_identity(self, setup_gallery):
        gallery_ids, gallery_mat, engine = setup_gallery
        accumulator = TrackEvidenceAccumulator(engine, min_observations=3)

        for _ in range(5):
            accumulator.add_observation(
                np.array([0.98, 0.02, 0.0, 0.0], dtype=np.float32),
                0.9,
                gallery_ids,
                gallery_mat,
            )
        assert accumulator.confirmed_identity == "worker_001"

        noisy_frame = np.array([0.10, 0.90, 0.0, 0.0], dtype=np.float32)
        dec = accumulator.add_observation(noisy_frame, 0.3, gallery_ids, gallery_mat)

        assert accumulator.confirmed_identity == "worker_001"

    def test_unknown_person_track_rejection(self, setup_gallery):
        gallery_ids, gallery_mat, engine = setup_gallery
        accumulator = TrackEvidenceAccumulator(engine, min_observations=3)

        unknown_vec = np.array([0.1, 0.1, 0.98, 0.0], dtype=np.float32)

        for _ in range(4):
            dec = accumulator.add_observation(unknown_vec, 0.85, gallery_ids, gallery_mat)

        assert dec.is_accepted is False
        assert accumulator.confirmed_identity is None
        assert "Score below threshold" in dec.rejection_reason
