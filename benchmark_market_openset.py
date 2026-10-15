import os
import sys
import json
import argparse
import numpy as np
import torch
from torch.utils.data import DataLoader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openset_reid.data.market1501 import build_market1501_openset_protocol
from openset_reid.models.openset_model import create_openset_model
from openset_reid.evaluation.metrics import OpenSetEvaluationMetrics

def extract_features(model, dataloader, device='cuda'):
    model.eval()
    all_feats = []
    with torch.no_grad():
        for imgs, _, _, _ in dataloader:
            imgs = imgs.to(device)
            feats = model.extract_features(imgs)
            all_feats.append(feats.cpu().numpy())
    return np.vstack(all_feats)

def evaluate_market_openset(model_path: str, market_dir: str='D:\\zed digital\\Market-1501-v15.09.15\\Market-1501-v15.09.15', num_enrolled: int=250, batch_size: int=64, device: str='cuda', tag: str='before_update'):
    print(f"\n{'=' * 70}")
    print(f'  BENCHMARKING MODEL ON MARKET-1501 OPEN-SET: [{tag.upper()}]')
    print(f'  Model Checkpoint: {model_path}')
    print(f"{'=' * 70}")
    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    num_classes = ckpt.get('num_classes', 751)
    cfg = ckpt.get('config', None)
    dual_gran = getattr(cfg, 'use_dual_granularity', True) if cfg else True
    emb_dim = getattr(cfg, 'embedding_dim', 512) if cfg else 512
    model = create_openset_model(num_classes=num_classes, dual_granularity=dual_gran, embedding_dim=emb_dim).to(device)
    state_dict = ckpt['model_state_dict'] if 'model_state_dict' in ckpt else ckpt
    model_state = model.state_dict()
    filtered_state = {k: v for k, v in state_dict.items() if k in model_state and v.shape == model_state[k].shape}
    model.load_state_dict(filtered_state, strict=False)
    model.eval()
    print(f'Loaded {len(filtered_state)}/{len(model_state)} layers from checkpoint.')
    print(f'Setting up Market-1501 Open-Set Protocol (N={num_enrolled} enrolled IDs)...')
    protocol = build_market1501_openset_protocol(market_dir, num_enrolled_pids=num_enrolled, seed=42)
    gal_loader = DataLoader(protocol['gallery_dataset'], batch_size=batch_size, shuffle=False, num_workers=0)
    gen_loader = DataLoader(protocol['genuine_dataset'], batch_size=batch_size, shuffle=False, num_workers=0)
    imp_loader = DataLoader(protocol['impostor_dataset'], batch_size=batch_size, shuffle=False, num_workers=0)
    print(f"Dataset Protocol: {len(protocol['gallery_raw'])} Gallery Images | {len(protocol['genuine_raw'])} Genuine Queries | {len(protocol['impostor_raw'])} Impostor Queries")
    print('Extracting feature embeddings on GPU...')
    t0 = torch.cuda.Event(enable_timing=True)
    t1 = torch.cuda.Event(enable_timing=True)
    t0.record()
    gal_feats = extract_features(model, gal_loader, device=device)
    gen_feats = extract_features(model, gen_loader, device=device)
    imp_feats = extract_features(model, imp_loader, device=device)
    t1.record()
    torch.cuda.synchronize()
    extract_time = t0.elapsed_time(t1) / 1000.0
    print(f'Extracted {len(gal_feats) + len(gen_feats) + len(imp_feats)} embeddings in {extract_time:.2f}s ({len(gal_feats) + len(gen_feats) + len(imp_feats) / max(1e-05, extract_time):.1f} crops/sec).')
    gal_pids = np.array([it[1] for it in protocol['gallery_raw']])
    gen_pids = np.array([it[1] for it in protocol['genuine_raw']])
    imp_pids = np.array([it[1] for it in protocol['impostor_raw']])
    gen_sims = np.dot(gen_feats, gal_feats.T)
    imp_sims = np.dot(imp_feats, gal_feats.T)
    rank1_correct = 0
    rank5_correct = 0
    aps = []
    for i in range(len(gen_sims)):
        sim_row = gen_sims[i]
        true_pid = gen_pids[i]
        sorted_indices = np.argsort(-sim_row)
        sorted_pids = gal_pids[sorted_indices]
        if sorted_pids[0] == true_pid:
            rank1_correct += 1
        if true_pid in sorted_pids[:5]:
            rank5_correct += 1
        matches = sorted_pids == true_pid
        if np.sum(matches) > 0:
            cum_matches = np.cumsum(matches)
            ranks = np.arange(1, len(sorted_pids) + 1)
            precision_at_k = cum_matches / ranks
            ap = np.sum(precision_at_k * matches) / np.sum(matches)
            aps.append(ap)
    rank1 = rank1_correct / len(gen_sims)
    rank5 = rank5_correct / len(gen_sims)
    map_score = np.mean(aps) if len(aps) > 0 else 0.0
    genuine_scores = []
    for i in range(len(gen_sims)):
        matches = gal_pids == gen_pids[i]
        if np.sum(matches) > 0:
            genuine_scores.append(float(np.max(gen_sims[i][matches])))
        else:
            genuine_scores.append(float(np.max(gen_sims[i])))
    genuine_scores = np.array(genuine_scores)
    impostor_scores = np.max(imp_sims, axis=1)
    far_curve, tar_curve, thresholds, roc_auc = OpenSetEvaluationMetrics.compute_roc_curve(genuine_scores, impostor_scores)
    eer, _ = OpenSetEvaluationMetrics.compute_equal_error_rate(far_curve, tar_curve)
    far_at_recall = OpenSetEvaluationMetrics.compute_far_at_fixed_recall(far_curve, tar_curve, target_recalls=[0.8, 0.85, 0.9, 0.95, 0.99])
    tar_at_far = OpenSetEvaluationMetrics.compute_tar_at_fixed_far(far_curve, tar_curve, target_fars=[0.01, 0.05, 0.1, 0.15, 0.2, 0.25])
    idx_20 = int(np.argmin(np.abs(far_curve - 0.2)))
    report = {'tag': tag, 'model_path': model_path, 'num_enrolled': num_enrolled, 'roc_auc': float(roc_auc), 'eer': float(eer), 'closed_set_rank1': float(rank1), 'closed_set_rank5': float(rank5), 'closed_set_map': float(map_score), 'far_at_recall': {str(k): float(v) for k, v in far_at_recall.items()}, 'tar_at_far': {str(k): float(v) for k, v in tar_at_far.items()}, 'target_20_point': {'threshold': float(thresholds[idx_20]), 'actual_far': float(far_curve[idx_20]), 'genuine_recall_tar': float(tar_curve[idx_20]), 'impostor_rejection_rate': float(1.0 - far_curve[idx_20])}, 'genuine_scores': genuine_scores.tolist(), 'impostor_scores': impostor_scores.tolist(), 'far_curve': far_curve.tolist(), 'tar_curve': tar_curve.tolist(), 'thresholds': thresholds.tolist()}
    print(f"\n{'-' * 70}")
    print(f'  RESULTS SUMMARY: [{tag.upper()}]')
    print(f"{'-' * 70}")
    print(f"  ROC AUC:               {report['roc_auc']:.4f}")
    print(f"  Equal Error Rate (EER):{report['eer'] * 100:.2f}%")
    print(f"  Closed-Set Rank-1:     {report['closed_set_rank1'] * 100:.2f}%")
    print(f"  Closed-Set Rank-5:     {report['closed_set_rank5'] * 100:.2f}%")
    print(f"  Closed-Set mAP:        {report['closed_set_map'] * 100:.2f}%")
    print(f"  FAR @ Recall=90%:      {report['far_at_recall'].get('0.9', 1.0) * 100:.2f}%")
    print(f"  FAR @ Recall=95%:      {report['far_at_recall'].get('0.95', 1.0) * 100:.2f}%")
    print(f"  TAR @ FAR=1%:          {report['tar_at_far'].get('0.01', 0.0) * 100:.2f}%")
    print(f"  TAR @ FAR=5%:          {report['tar_at_far'].get('0.05', 0.0) * 100:.2f}%")
    print(f"  TAR @ FAR=20%:         {report['tar_at_far'].get('0.2', 0.0) * 100:.2f}%")
    print(f"  Target 20% FAR Point:  FAR = {report['target_20_point']['actual_far'] * 100:.2f}% | Genuine Recall (TAR) = {report['target_20_point']['genuine_recall_tar'] * 100:.2f}% (Threshold: {report['target_20_point']['threshold']:.4f})")
    print(f"{'=' * 70}\n")
    out_json = f'experiments/reports/market1501_{tag}_benchmark.json'
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'Benchmark results saved to {out_json}')
    return report
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, required=True, help='Path to model checkpoint')
    parser.add_argument('--tag', type=str, default='before_update', help='Experiment tag: before_update or after_update')
    parser.add_argument('--market-dir', type=str, default='D:\\zed digital\\Market-1501-v15.09.15\\Market-1501-v15.09.15')
    parser.add_argument('--enrolled', type=int, default=250)
    args = parser.parse_args()
    evaluate_market_openset(model_path=args.model, market_dir=args.market_dir, num_enrolled=args.enrolled, tag=args.tag)
