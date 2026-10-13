"""
Extreme Value Theory (EVT) Weibull Tail Calibration for Open-Set Recognition.
Based on the Statistical Extreme Value Theorem: the distribution of maximum
similarities to impostor / non-target classes follows a Weibull / Gumbel tail.
Provides mathematically sound p-values for unknown-identity rejection.
"""

import numpy as np
from scipy.stats import weibull_min
from typing import Tuple, List, Optional, Union
import torch


class EVTTailCalibrator:
    """
    Fits Weibull distribution to the upper tail of impostor similarity scores.
    Allows testing hypothesis:
        H0: Probe q is an unknown / unenrolled identity
        H1: Probe q is genuine enrolled identity g*
    """
    def __init__(self, tail_size: int = 20, confidence_level: float = 0.99):
        """
        Args:
            tail_size: Number of extreme tail distances used to fit Weibull.
            confidence_level: Desired rejection significance.
        """
        self.tail_size = tail_size
        self.confidence_level = confidence_level
        self.weibull_params = None  # (c, loc, scale)

    def fit_tail(self, non_match_distances: np.ndarray) -> bool:
        """
        Fits Weibull distribution to SMALLEST non-match distances
        (the dangerous extreme tail where impostors are closest to gallery).

        Args:
            non_match_distances: 1D array of non-target Euclidean distances.
        """
        if len(non_match_distances) < self.tail_size:
            return False

        # Sort ascending: smallest impostor distances = most dangerous
        sorted_dists = np.sort(non_match_distances)
        tail_data = sorted_dists[:self.tail_size]
        tail_data = tail_data[tail_data > 1e-6]  # remove exact zeros
        if len(tail_data) < 5:
            return False

        try:
            c, loc, scale = weibull_min.fit(tail_data, floc=0)
            self.weibull_params = (float(c), float(loc), max(float(scale), 1e-4))
            return True
        except Exception:
            mean_dist = float(np.mean(tail_data))
            self.weibull_params = (1.0, 0.0, max(mean_dist, 1e-4))
            return True

    def compute_outlier_probability(self, distance: float) -> float:
        """
        P(Impostor Distance <= distance | Impostor distribution)
        = CDF of the Weibull tail at this distance.

        High value => many impostors land this close => suspicious, likely reject.
        Low value  => very few impostors ever get this close => genuine-like, accept.
        """
        if self.weibull_params is None:
            return 0.5  # unknown -> neutral

        c, loc, scale = self.weibull_params
        if scale <= 1e-6:
            return 0.5

        p_val = weibull_min.cdf(distance, c, loc=loc, scale=scale)
        return float(np.clip(p_val, 0.0, 1.0))

    def compute_evt_score(self, distance: float) -> float:
        """
        EVT match confidence score in [0, 1].
        High score = the query is CLOSER than the impostor tail => genuine-like.
        Low score  = impostors routinely achieve this distance => reject.
        """
        p_val = self.compute_outlier_probability(distance)
        # 1 - p_val: if few impostors are this close, score is high (genuine)
        return float(np.clip(1.0 - p_val, 0.0, 1.0))
