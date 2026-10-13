"""
Comprehensive Open-Set Re-Identification Evaluation Metrics.
Implements:
1. ROC Analysis (TAR vs. FAR curve)
2. Detection Error Tradeoff (DET: FRR vs. FAR)
3. Fixed-Recall Operating Points (FAR @ Recall = 85%, 90%, 95%, 99%)
4. Fixed-FAR Operating Points (TAR @ FAR = 0.01%, 0.1%, 1.0%, 5.0%)
5. Closed-set Rank-1, Rank-5, and mAP
6. Calibration Metrics: Expected Calibration Error (ECE) and Brier Score
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from sklearn.metrics import roc_curve, auc, brier_score_loss


class OpenSetEvaluationMetrics:
    """
    Computes rigorous biometrics and open-set recognition metrics.
    """
    @staticmethod
    def compute_roc_curve(genuine_scores: np.ndarray,
                          impostor_scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Computes ROC curve (TAR vs FAR).
        
        Args:
            genuine_scores: 1D array of scores for genuine (known probe matching true gallery) pairs
            impostor_scores: 1D array of scores for impostor / unknown probe matches
        Returns:
            far, tar, thresholds, roc_auc
        """
        y_true = np.concatenate([np.ones_like(genuine_scores), np.zeros_like(impostor_scores)])
        y_scores = np.concatenate([genuine_scores, impostor_scores])

        # roc_curve returns fpr (far), tpr (tar), thresholds
        far, tar, thresholds = roc_curve(y_true, y_scores, pos_label=1)
        roc_auc = float(auc(far, tar))
        return far, tar, thresholds, roc_auc

    @staticmethod
    def compute_far_at_fixed_recall(far: np.ndarray,
                                   tar: np.ndarray,
                                   target_recalls: List[float] = [0.85, 0.90, 0.95, 0.99]) -> Dict[float, float]:
        """
        Finds the minimum False Accept Rate (FAR) achieved at fixed Target Recalls (TAR).
        Critical metric specified in problem statement.
        """
        results = {}
        for target in target_recalls:
            # Indices where tar >= target
            valid_indices = np.where(tar >= target)[0]
            if len(valid_indices) > 0:
                # Minimum FAR at or above this recall level
                min_far = float(np.min(far[valid_indices]))
            else:
                min_far = 1.0
            results[target] = min_far
        return results

    @staticmethod
    def compute_tar_at_fixed_far(far: np.ndarray,
                                 tar: np.ndarray,
                                 target_fars: List[float] = [0.0001, 0.001, 0.01, 0.05]) -> Dict[float, float]:
        """
        Finds the maximum True Accept Rate (TAR) achieved at fixed low False Accept Rates.
        """
        results = {}
        for target in target_fars:
            valid_indices = np.where(far <= target)[0]
            if len(valid_indices) > 0:
                max_tar = float(np.max(tar[valid_indices]))
            else:
                max_tar = 0.0
            results[target] = max_tar
        return results

    @staticmethod
    def compute_equal_error_rate(far: np.ndarray, tar: np.ndarray) -> Tuple[float, float]:
        """
        Calculates Equal Error Rate (EER) where FAR == FRR (1 - TAR).
        Returns eer, threshold_idx
        """
        frr = 1.0 - tar
        idx = np.nanargmin(np.abs(far - frr))
        eer = float((far[idx] + frr[idx]) / 2.0)
        return eer, float(far[idx])

    @staticmethod
    def compute_calibration_metrics(predicted_probs: np.ndarray,
                                    true_labels: np.ndarray,
                                    num_bins: int = 10) -> Dict[str, float]:
        """
        Computes Expected Calibration Error (ECE) and Brier Score.
        """
        predicted_probs = np.clip(predicted_probs, 0.0, 1.0)
        true_labels = true_labels.astype(int)

        brier = float(brier_score_loss(true_labels, predicted_probs))

        # ECE computation
        bin_edges = np.linspace(0.0, 1.0, num_bins + 1)
        ece = 0.0
        total_samples = len(predicted_probs)

        for i in range(num_bins):
            bin_mask = (predicted_probs >= bin_edges[i]) & (predicted_probs < bin_edges[i + 1])
            if i == num_bins - 1:
                bin_mask = bin_mask | (predicted_probs == bin_edges[i + 1])

            bin_size = np.sum(bin_mask)
            if bin_size > 0:
                bin_acc = np.mean(true_labels[bin_mask])
                bin_conf = np.mean(predicted_probs[bin_mask])
                ece += (bin_size / total_samples) * np.abs(bin_acc - bin_conf)

        return {
            "brier_score": brier,
            "ece": float(ece)
        }

    @staticmethod
    def compute_closed_set_cmc_and_map(query_feats: np.ndarray,
                                       query_pids: List[str],
                                       gallery_feats: np.ndarray,
                                       gallery_pids: List[str]) -> Tuple[Dict[int, float], float]:
        """
        Computes standard closed-set Cumulative Matching Characteristic (CMC)
        and mean Average Precision (mAP).
        """
        # Similarity matrix: [N_q, N_g]
        sim_mat = np.dot(query_feats, gallery_feats.T)
        num_q = len(query_pids)
        num_g = len(gallery_pids)

        rank1 = 0
        rank5 = 0
        all_ap = []

        for q_idx in range(num_q):
            q_pid = query_pids[q_idx]
            order = np.argsort(sim_mat[q_idx])[::-1]
            match_mask = np.array([gallery_pids[g_idx] == q_pid for g_idx in order])

            if match_mask[0]:
                rank1 += 1
            if np.any(match_mask[:min(5, num_g)]):
                rank5 += 1

            # Average precision
            if np.any(match_mask):
                cumsum = np.cumsum(match_mask)
                ranks = np.arange(1, len(match_mask) + 1)
                precision_at_k = cumsum / ranks
                ap = np.sum(precision_at_k * match_mask) / np.sum(match_mask)
                all_ap.append(ap)
            else:
                all_ap.append(0.0)

        cmc = {
            1: float(rank1 / num_q),
            5: float(rank5 / num_q)
        }
        mean_ap = float(np.mean(all_ap)) if len(all_ap) > 0 else 0.0
        return cmc, mean_ap
