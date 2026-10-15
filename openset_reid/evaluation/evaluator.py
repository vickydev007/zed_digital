import os
import numpy as np
import torch
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
from openset_reid.evaluation.metrics import OpenSetEvaluationMetrics
from openset_reid.open_set.calibrator import OpenSetMatcher

class BenchmarkEvaluator:

    def __init__(self, model, device: str='cpu'):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()

    def extract_features_from_dataset(self, dataloader) -> Tuple[np.ndarray, List[str], List[str]]:
        all_feats = []
        all_pids = []
        all_paths = []
        with torch.no_grad():
            for images, labels, pids, paths in dataloader:
                images = images.to(self.device)
                feats = self.model.extract_features(images)
                all_feats.append(feats.cpu().numpy())
                all_pids.extend(pids)
                all_paths.extend(paths)
        if len(all_feats) == 0:
            return (np.zeros((0, 512)), [], [])
        features = np.vstack(all_feats)
        return (features, all_pids, all_paths)

    def evaluate_protocol(self, gallery_feats: np.ndarray, gallery_pids: List[str], enrolled_feats: np.ndarray, enrolled_pids: List[str], impostor_feats: np.ndarray, impostor_pids: List[str], cohort_feats: Optional[np.ndarray]=None, use_contrast_margin: bool=True, use_cohort: bool=True, use_evt: bool=True) -> Dict:
        matcher = OpenSetMatcher(score_threshold=0.5, margin_threshold=0.04, evt_threshold=0.4, use_cohort=use_cohort, use_evt=use_evt, use_margin=use_contrast_margin)
        matcher.enroll_batch(gallery_pids, gallery_feats)
        if cohort_feats is not None and use_cohort:
            matcher.set_cohort_bank(cohort_feats)
        sim_mat_enrolled = np.dot(enrolled_feats, gallery_feats.T)
        genuine_scores = []
        genuine_margins = []
        wrong_accepted_as_other = 0
        for q_idx, q_pid in enumerate(enrolled_pids):
            scores = sim_mat_enrolled[q_idx]
            q_emb = enrolled_feats[q_idx]
            dec = matcher.match(q_emb)
            true_mask = np.array([pid == q_pid for pid in gallery_pids])
            if np.any(true_mask):
                max_true_sim = np.max(scores[true_mask])
                non_true_mask = ~true_mask
                max_other_sim = np.max(scores[non_true_mask]) if np.any(non_true_mask) else 0.0
                margin = max_true_sim - max_other_sim
                genuine_scores.append(max_true_sim)
                genuine_margins.append(margin)
        genuine_scores = np.array(genuine_scores, dtype=np.float32)
        genuine_margins = np.array(genuine_margins, dtype=np.float32)
        sim_mat_impostor = np.dot(impostor_feats, gallery_feats.T)
        impostor_scores = []
        impostor_margins = []
        if use_evt:
            all_imp_dists = np.sqrt(np.maximum(2.0 - 2.0 * sim_mat_impostor.ravel(), 0.0))
            matcher.fit_evt_from_distances(all_imp_dists)
        for q_idx in range(len(impostor_pids)):
            scores = sim_mat_impostor[q_idx]
            q_emb = impostor_feats[q_idx]
            dec = matcher.match(q_emb)
            sorted_scores = np.sort(scores)[::-1]
            top_imp_sim = sorted_scores[0]
            second_imp_sim = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
            margin = top_imp_sim - second_imp_sim
            impostor_scores.append(top_imp_sim)
            impostor_margins.append(margin)
        impostor_scores = np.array(impostor_scores, dtype=np.float32)
        impostor_margins = np.array(impostor_margins, dtype=np.float32)
        if use_contrast_margin:
            gen_eval_scores = genuine_scores + 0.8 * np.maximum(genuine_margins, 0.0)
            imp_eval_scores = impostor_scores + 0.8 * np.maximum(impostor_margins, 0.0)
        else:
            gen_eval_scores = genuine_scores
            imp_eval_scores = impostor_scores
        far, tar, thresholds, roc_auc = OpenSetEvaluationMetrics.compute_roc_curve(gen_eval_scores, imp_eval_scores)
        far_at_recall = OpenSetEvaluationMetrics.compute_far_at_fixed_recall(far, tar, target_recalls=[0.85, 0.9, 0.95, 0.99])
        tar_at_far = OpenSetEvaluationMetrics.compute_tar_at_fixed_far(far, tar, target_fars=[0.001, 0.01, 0.05, 0.1])
        eer, _ = OpenSetEvaluationMetrics.compute_equal_error_rate(far, tar)
        cmc, mean_ap = OpenSetEvaluationMetrics.compute_closed_set_cmc_and_map(enrolled_feats, enrolled_pids, gallery_feats, gallery_pids)
        results = {'roc_auc': roc_auc, 'eer': eer, 'far_at_recall': far_at_recall, 'tar_at_far': tar_at_far, 'closed_set_rank1': cmc[1], 'closed_set_rank5': cmc[5], 'closed_set_map': mean_ap, 'far_curve': far, 'tar_curve': tar, 'thresholds': thresholds, 'genuine_scores': genuine_scores, 'impostor_scores': impostor_scores, 'genuine_margins': genuine_margins, 'impostor_margins': impostor_margins}
        return results

    @staticmethod
    def plot_roc_curves(experiments_dict: Dict[str, Dict], save_path: str):
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
        ax1 = axes[0]
        for name, res in experiments_dict.items():
            far = res['far_curve']
            tar = res['tar_curve']
            auc_val = res['roc_auc']
            ax1.plot(far, tar, lw=2.2, label=f'{name} (AUC={auc_val:.4f})')
        ax1.plot([0, 1], [0, 1], 'k--', lw=1, alpha=0.5, label='Random Guess')
        ax1.set_xlabel('False Accept Rate (FAR)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('True Accept Rate (Recall / TAR)', fontsize=12, fontweight='bold')
        ax1.set_title('Open-Set ROC: Low Inter-Class Variance (Same-Clothing)', fontsize=13, fontweight='bold')
        ax1.set_xlim([0.0, 1.0])
        ax1.set_ylim([0.0, 1.02])
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.legend(loc='lower right', framealpha=0.9)
        ax2 = axes[1]
        for name, res in experiments_dict.items():
            far = res['far_curve']
            tar = res['tar_curve']
            ax2.semilogx(np.maximum(far, 0.0001), tar, lw=2.2, label=name)
        ax2.set_xlabel('False Accept Rate (FAR, Log Scale)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('True Accept Rate (TAR)', fontsize=12, fontweight='bold')
        ax2.set_title('Operational Rejection Regime (Low FAR)', fontsize=13, fontweight='bold')
        ax2.set_xlim([0.001, 1.0])
        ax2.set_ylim([0.2, 1.02])
        ax2.grid(True, which='both', linestyle='--', alpha=0.6)
        ax2.legend(loc='lower right', framealpha=0.9)
        plt.tight_layout()
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        plt.savefig(save_path, bbox_inches='tight')
        plt.close()
