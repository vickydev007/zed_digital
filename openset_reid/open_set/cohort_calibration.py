import numpy as np
import torch
from typing import Optional, Union, Tuple

class CohortCalibrator:

    def __init__(self, cohort_embeddings: Optional[np.ndarray]=None, eps: float=1e-06):
        self.cohort = None
        self.eps = eps
        if cohort_embeddings is not None:
            self.set_cohort(cohort_embeddings)

    def set_cohort(self, cohort_embeddings: Union[np.ndarray, torch.Tensor]):
        if isinstance(cohort_embeddings, torch.Tensor):
            cohort_embeddings = cohort_embeddings.detach().cpu().numpy()
        norms = np.linalg.norm(cohort_embeddings, axis=1, keepdims=True)
        self.cohort = cohort_embeddings / np.maximum(norms, self.eps)

    def is_ready(self) -> bool:
        return self.cohort is not None and len(self.cohort) > 0

    def compute_probe_stats(self, query_emb: np.ndarray) -> Tuple[float, float]:
        if not self.is_ready():
            return (0.0, 1.0)
        sims = np.dot(self.cohort, query_emb)
        mean_sim = float(np.mean(sims))
        std_sim = float(np.std(sims))
        return (mean_sim, max(std_sim, self.eps))

    def normalize_scores(self, query_emb: np.ndarray, raw_similarities: np.ndarray) -> np.ndarray:
        if not self.is_ready():
            return raw_similarities
        mu_q, sigma_q = self.compute_probe_stats(query_emb)
        z_scores = (raw_similarities - mu_q) / sigma_q
        return z_scores
