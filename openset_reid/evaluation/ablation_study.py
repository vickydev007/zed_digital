import os
import json
import torch
import numpy as np
from torch.utils.data import DataLoader
from typing import Dict, List
from openset_reid.data.dataset import ReIDImageDataset
from openset_reid.models.openset_model import create_openset_model
from openset_reid.training.config import TrainingConfig
from openset_reid.training.trainer import OpenSetTrainer
from openset_reid.evaluation.evaluator import BenchmarkEvaluator

class AblationExperimentSuite:

    def __init__(self, data_dir: str, output_dir: str='d:/zed digital/experiments/ablation'):
        self.data_dir = data_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def run_all(self, epochs: int=12) -> Dict[str, Dict]:
        print('=' * 80)
        print('RUNNING COMPREHENSIVE ABLATION STUDY: OPEN-SET RE-ID UNDER LOW VARIANCE')
        print('=' * 80)
        gallery_loader = DataLoader(ReIDImageDataset(os.path.join(self.data_dir, 'gallery'), is_train=False), batch_size=32, shuffle=False)
        enrolled_query_loader = DataLoader(ReIDImageDataset(os.path.join(self.data_dir, 'query_enrolled'), is_train=False), batch_size=32, shuffle=False)
        impostor_query_loader = DataLoader(ReIDImageDataset(os.path.join(self.data_dir, 'query_impostor'), is_train=False), batch_size=32, shuffle=False)
        cohort_loader = DataLoader(ReIDImageDataset(os.path.join(self.data_dir, 'cohort'), is_train=False), batch_size=32, shuffle=False)
        experiments = [{'name': '1. Baseline (Global + Uncalibrated)', 'dual_granularity': False, 'arcface_margin': 0.0, 'w_triplet': 0.0, 'use_contrast_margin': False, 'use_cohort': False, 'use_evt': False}, {'name': '2. + ArcFace Angular Margin', 'dual_granularity': False, 'arcface_margin': 0.35, 'w_triplet': 0.0, 'use_contrast_margin': False, 'use_cohort': False, 'use_evt': False}, {'name': '3. + Dual-Granularity (Part Orthogonal)', 'dual_granularity': True, 'arcface_margin': 0.35, 'w_triplet': 0.5, 'use_contrast_margin': False, 'use_cohort': False, 'use_evt': False}, {'name': '4. + Adaptive Hard Mining', 'dual_granularity': True, 'arcface_margin': 0.35, 'w_triplet': 1.0, 'use_contrast_margin': False, 'use_cohort': False, 'use_evt': False}, {'name': '5. Full Proposed System (Calibrated Boundary)', 'dual_granularity': True, 'arcface_margin': 0.35, 'w_triplet': 1.0, 'use_contrast_margin': True, 'use_cohort': True, 'use_evt': True}]
        results_summary = {}
        for exp in experiments:
            name = exp['name']
            print(f'\n--- Running Experiment: {name} ---')
            cfg = TrainingConfig(data_dir=self.data_dir, output_dir=os.path.join(self.output_dir, name.replace(' ', '_').replace('+', 'plus')), use_dual_granularity=exp['dual_granularity'], arcface_margin=exp['arcface_margin'], w_triplet=exp['w_triplet'], num_epochs=epochs)
            trainer = OpenSetTrainer(cfg)
            trainer.run()
            evaluator = BenchmarkEvaluator(trainer.model, device='cpu')
            gal_feats, gal_pids, _ = evaluator.extract_features_from_dataset(gallery_loader)
            enr_feats, enr_pids, _ = evaluator.extract_features_from_dataset(enrolled_query_loader)
            imp_feats, imp_pids, _ = evaluator.extract_features_from_dataset(impostor_query_loader)
            coh_feats, coh_pids, _ = evaluator.extract_features_from_dataset(cohort_loader)
            res = evaluator.evaluate_protocol(gallery_feats=gal_feats, gallery_pids=gal_pids, enrolled_feats=enr_feats, enrolled_pids=enr_pids, impostor_feats=imp_feats, impostor_pids=imp_pids, cohort_feats=coh_feats, use_contrast_margin=exp['use_contrast_margin'], use_cohort=exp['use_cohort'], use_evt=exp['use_evt'])
            results_summary[name] = res
            print(f"[{name}] AUC: {res['roc_auc']:.4f} | EER: {res['eer'] * 100:.2f}% | FAR@Rec=90%: {res['far_at_recall'].get(0.9, 1.0) * 100:.2f}% | TAR@FAR=1%: {res['tar_at_far'].get(0.01, 0.0) * 100:.2f}%")
        roc_plot_path = os.path.join(self.output_dir, 'ablation_roc_comparison.png')
        BenchmarkEvaluator.plot_roc_curves(results_summary, roc_plot_path)
        print(f'\nAblation ROC curve saved to {roc_plot_path}')
        return results_summary
