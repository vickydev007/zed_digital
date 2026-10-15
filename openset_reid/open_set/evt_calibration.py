import numpy as np
from scipy.stats import weibull_min
from typing import Tuple, List, Optional, Union
import torch

class EVTTailCalibrator:

    def __init__(self, tail_size: int=20, confidence_level: float=0.99):
        self.tail_size = tail_size
        self.confidence_level = confidence_level
        self.weibull_params = None

    def fit_tail(self, non_match_distances: np.ndarray) -> bool:
        if len(non_match_distances) < self.tail_size:
            return False
        sorted_dists = np.sort(non_match_distances)
        tail_data = sorted_dists[:self.tail_size]
        tail_data = tail_data[tail_data > 1e-06]
        if len(tail_data) < 5:
            return False
        try:
            c, loc, scale = weibull_min.fit(tail_data, floc=0)
            self.weibull_params = (float(c), float(loc), max(float(scale), 0.0001))
            return True
        except Exception:
            mean_dist = float(np.mean(tail_data))
            self.weibull_params = (1.0, 0.0, max(mean_dist, 0.0001))
            return True

    def compute_outlier_probability(self, distance: float) -> float:
        if self.weibull_params is None:
            return 0.5
        c, loc, scale = self.weibull_params
        if scale <= 1e-06:
            return 0.5
        p_val = weibull_min.cdf(distance, c, loc=loc, scale=scale)
        return float(np.clip(p_val, 0.0, 1.0))

    def compute_evt_score(self, distance: float) -> float:
        p_val = self.compute_outlier_probability(distance)
        return float(np.clip(1.0 - p_val, 0.0, 1.0))
