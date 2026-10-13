"""
Unified Open-Set Calibrator and Real-Time Matcher.
Transforms raw hyperspherical similarities into calibrated probabilities,
integrates EVT tail modeling, Cohort normalization, and margin boundaries.
"""

import numpy as np
import torch
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional, Union
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression

from openset_reid.open_set.evt_calibration import EVTTailCalibrator
from openset_reid.open_set.cohort_calibration import CohortCalibrator
from openset_reid.open_set.decision_boundary import OpenSetDecisionEngine, MatchDecision


class ConfidenceCalibrator:
    """
    Platt Scaling & Isotonic Calibration:
    Fits an empirical mapping from raw/normalized similarity scores to true match probabilities.
    Minimizes Brier Score and Expected Calibration Error (ECE).
    """
    def __init__(self, method: str = "platt"):
        self.method = method
        self.platt_model = None
        self.iso_model = None
        self.is_fitted = False

    def fit(self, scores: np.ndarray, labels: np.ndarray):
        """
        Args:
            scores: [N] 1D array of similarity scores
            labels: [N] binary 1 (true match) or 0 (impostor / non-match)
        """
        scores = np.asarray(scores).reshape(-1, 1)
        labels = np.asarray(labels).astype(int)

        if self.method == "platt":
            self.platt_model = LogisticRegression(C=1.0, max_iter=1000)
            self.platt_model.fit(scores, labels)
        elif self.method == "isotonic":
            self.iso_model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.iso_model.fit(scores.ravel(), labels)
        self.is_fitted = True

    def predict_probability(self, scores: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Converts similarity scores into calibrated match probabilities in [0, 1].
        """
        single_input = isinstance(scores, (float, int, np.floating, np.float32, np.float64))
        scores_arr = np.atleast_1d(np.asarray(scores, dtype=np.float64)).ravel()  # always 1-D

        if not self.is_fitted:
            # Fallback sigmoid heuristic centered at 0.70 with temperature 0.08
            probs = 1.0 / (1.0 + np.exp(-(scores_arr - 0.70) / 0.08))
        elif self.method == "platt":
            probs = self.platt_model.predict_proba(scores_arr.reshape(-1, 1))[:, 1]
        elif self.method == "isotonic":
            probs = self.iso_model.predict(scores_arr)
        else:
            probs = scores_arr

        probs = np.clip(probs, 0.0, 1.0)
        return float(probs[0]) if single_input else probs


class OpenSetMatcher:
    """
    High-Performance Open-Set Re-Identification Engine.
    Maintains:
    - Dynamic enrolled gallery (supports streaming enrollment & multi-exemplar templates)
    - CohortCalibrator for background uniform bias cancellation
    - EVTTailCalibrator for extreme value tail hypothesis testing
    - ConfidenceCalibrator for Platt/Isotonic probabilities
    - OpenSetDecisionEngine for multi-criterion margin boundary
    """
    def __init__(self,
                 score_threshold: float = 0.65,
                 margin_threshold: float = 0.06,
                 evt_threshold: float = 0.50,
                 use_cohort: bool = True,
                 use_evt: bool = True,
                 use_margin: bool = True):
        self.decision_engine = OpenSetDecisionEngine(
            score_threshold=score_threshold,
            margin_threshold=margin_threshold,
            evt_threshold=evt_threshold,
            use_contrast_margin=use_margin,
            use_evt=use_evt
        )
        self.confidence_calibrator = ConfidenceCalibrator(method="platt")
        self.cohort_calibrator = CohortCalibrator()
        self.evt_calibrator = EVTTailCalibrator(tail_size=25)

        self.use_cohort = use_cohort
        self.use_evt = use_evt

        # Gallery state
        self.gallery_embeddings: List[np.ndarray] = []  # each is [D]
        self.gallery_identities: List[str] = []
        self.gallery_matrix: Optional[np.ndarray] = None  # [N_gal, D]

    def enroll(self, identity: str, embedding: Union[np.ndarray, torch.Tensor]):
        """
        Enrolls a new exemplar template into the gallery.
        """
        if isinstance(embedding, torch.Tensor):
            embedding = embedding.detach().cpu().numpy()
        emb = embedding.astype(np.float32).ravel()
        emb = emb / max(np.linalg.norm(emb), 1e-6)

        self.gallery_embeddings.append(emb)
        self.gallery_identities.append(identity)
        self.gallery_matrix = np.vstack(self.gallery_embeddings)

    def enroll_batch(self, identities: List[str], embeddings: Union[np.ndarray, torch.Tensor]):
        if isinstance(embeddings, torch.Tensor):
            embeddings = embeddings.detach().cpu().numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norm_embs = embeddings / np.maximum(norms, 1e-6)

        for i, ident in enumerate(identities):
            self.gallery_embeddings.append(norm_embs[i])
            self.gallery_identities.append(ident)
        self.gallery_matrix = np.vstack(self.gallery_embeddings)

    def set_cohort_bank(self, cohort_embeddings: Union[np.ndarray, torch.Tensor]):
        """Sets the background cohort bank for uniform bias cancellation."""
        self.cohort_calibrator.set_cohort(cohort_embeddings)

    def fit_evt_from_distances(self, impostor_distances: np.ndarray):
        """Fits EVT Weibull tail on impostor distances."""
        self.evt_calibrator.fit_tail(impostor_distances)

    def fit_confidence_calibrator(self, scores: np.ndarray, labels: np.ndarray):
        """Fits Platt scaling on validation matches."""
        self.confidence_calibrator.fit(scores, labels)

    def match(self, query_emb: Union[np.ndarray, torch.Tensor]) -> MatchDecision:
        """
        Matches a single query embedding against the open gallery.
        
        Args:
            query_emb: [D] unit feature vector
        Returns:
            MatchDecision dataclass
        """
        if isinstance(query_emb, torch.Tensor):
            query_emb = query_emb.detach().cpu().numpy()
        q = query_emb.astype(np.float32).ravel()
        q = q / max(np.linalg.norm(q), 1e-6)

        if self.gallery_matrix is None or len(self.gallery_identities) == 0:
            return MatchDecision(
                is_accepted=False,
                matched_identity=None,
                confidence=0.0,
                raw_score=0.0,
                contrast_margin=0.0,
                second_identity=None,
                rejection_reason="Empty gallery",
                evt_tail_score=0.0
            )

        # Raw cosine similarities: [N_gal]
        raw_similarities = np.dot(self.gallery_matrix, q)

        # Score normalization via cohort if enabled
        effective_scores = raw_similarities.copy()
        if self.use_cohort and self.cohort_calibrator.is_ready():
            # Apply cohort shrinkage / Z-score adjustment
            mu_c, sigma_c = self.cohort_calibrator.compute_probe_stats(q)
            # Centered around expected uniform baseline
            effective_scores = raw_similarities - (mu_c - 0.5)

        # Maximum candidate
        max_idx = np.argmax(effective_scores)
        top_score = float(effective_scores[max_idx])

        # Calibrated probability
        calibrated_prob = self.confidence_calibrator.predict_probability(top_score)

        # EVT Tail calculation
        # Euclidean distance = sqrt(2 - 2 * cos_sim)
        top_raw = float(raw_similarities[max_idx])
        dist = float(np.sqrt(max(2.0 - 2.0 * top_raw, 0.0)))
        evt_tail_score = self.evt_calibrator.compute_evt_score(dist) if self.use_evt else 1.0

        # Decision boundary evaluation
        decision = self.decision_engine.evaluate_match(
            gallery_ids=self.gallery_identities,
            scores=effective_scores,
            calibrated_confidence=calibrated_prob,
            evt_tail_score=evt_tail_score
        )
        return decision
