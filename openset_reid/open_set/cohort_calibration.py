"""
Background Cohort Score Normalization (Z-Norm / T-Norm / S-Norm).
Neutralizes score inflation caused by identical uniform colors.
"""

import numpy as np
import torch
from typing import Optional, Union, Tuple


class CohortCalibrator:
    """
    Cohort Normalizer:
    Maintains a cohort bank of background pedestrian embeddings
    (e.g. representative workers/personnel wearing the same uniform).
    Normalizes raw probe-gallery cosine similarities against the background distribution.
    """
    def __init__(self, cohort_embeddings: Optional[np.ndarray] = None, eps: float = 1e-6):
        """
        Args:
            cohort_embeddings: [M, D] array of unit-normalized background embeddings.
        """
        self.cohort = None
        self.eps = eps
        if cohort_embeddings is not None:
            self.set_cohort(cohort_embeddings)

    def set_cohort(self, cohort_embeddings: Union[np.ndarray, torch.Tensor]):
        if isinstance(cohort_embeddings, torch.Tensor):
            cohort_embeddings = cohort_embeddings.detach().cpu().numpy()
        # Ensure L2 normalized
        norms = np.linalg.norm(cohort_embeddings, axis=1, keepdims=True)
        self.cohort = cohort_embeddings / np.maximum(norms, self.eps)

    def is_ready(self) -> bool:
        return self.cohort is not None and len(self.cohort) > 0

    def compute_probe_stats(self, query_emb: np.ndarray) -> Tuple[float, float]:
        """
        Computes mean and std of query against background cohort.
        Args:
            query_emb: [D] unit vector
        Returns:
            mean_sim, std_sim
        """
        if not self.is_ready():
            return 0.0, 1.0

        sims = np.dot(self.cohort, query_emb)  # [M]
        mean_sim = float(np.mean(sims))
        std_sim = float(np.std(sims))
        return mean_sim, max(std_sim, self.eps)

    def normalize_scores(self, query_emb: np.ndarray, raw_similarities: np.ndarray) -> np.ndarray:
        """
        Applies Z-normalization:
        Z = (S - mu_cohort) / sigma_cohort
        
        Args:
            query_emb: [D] query embedding
            raw_similarities: array of raw cosine similarities to gallery
        Returns:
            calibrated_z_scores: array of normalized Z-scores
        """
        if not self.is_ready():
            return raw_similarities

        mu_q, sigma_q = self.compute_probe_stats(query_emb)
        z_scores = (raw_similarities - mu_q) / sigma_q
        return z_scores
