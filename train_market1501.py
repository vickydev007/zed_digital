import os
import sys
import time
import math
import argparse
from typing import Dict, List, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.cuda.amp import autocast, GradScaler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openset_reid.data.market1501 import build_market1501_train_dataset
from openset_reid.data.dataset import PKRandomIdentitySampler
from openset_reid.models.openset_model import create_openset_model
from openset_reid.models.loss import CombinedOpenSetLoss
from openset_reid.training.config import TrainingConfig

class Market1501Trainer:

    def __init__(self, market_dir: str='D:\\zed digital\\Market-1501-v15.09.15\\Market-1501-v15.09.15', pretrained_ckpt: str='experiments/best_model.pth', output_dir: str='experiments/market1501_updated', num_epochs: int=20, p_identities: int=16, k_instances: int=4, lr: float=0.00035, weight_decay: float=0.0005, warmup_epochs: int=2, device: str='cuda'):
        self.device = torch.device(device if torch.cuda.is_available() and device == 'cuda' else 'cpu')
        self.num_epochs = num_epochs
        self.warmup_epochs = warmup_epochs
        self.base_lr = lr
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        print(f"\n{'=' * 70}")
        print(f'  INITIALIZING MARKET-1501 TRAINING ON {self.device.type.upper()}')
        print(f'  Market-1501 Directory: {market_dir}')
        print(f'  Pretrained Checkpoint: {pretrained_ckpt}')
        print(f'  Batch Size: P={p_identities} x K={k_instances} = {p_identities * k_instances}')
        print(f"{'=' * 70}")
        print('Loading Market-1501 training dataset (bounding_box_train)...')
        self.train_dataset, self.pid2label = build_market1501_train_dataset(market_dir)
        self.num_classes = len(self.pid2label)
        print(f'Dataset Loaded: {len(self.train_dataset)} images across {self.num_classes} identities.')
        self.sampler = PKRandomIdentitySampler(self.train_dataset, p=p_identities, k=k_instances)
        self.train_loader = DataLoader(self.train_dataset, batch_size=p_identities * k_instances, sampler=self.sampler, num_workers=0, pin_memory=True if self.device.type == 'cuda' else False, drop_last=True)
        print(f'Creating OpenSetReIDModel with {self.num_classes} classes and Dual-Granularity...')
        self.model = create_openset_model(num_classes=self.num_classes, dual_granularity=True, embedding_dim=512).to(self.device)
        if pretrained_ckpt and os.path.exists(pretrained_ckpt):
            print(f'Transferring feature extractor weights from {pretrained_ckpt}...')
            ckpt = torch.load(pretrained_ckpt, map_location=self.device, weights_only=False)
            state_dict = ckpt.get('model_state_dict', ckpt)
            model_state = self.model.state_dict()
            transferred = 0
            for k, v in state_dict.items():
                if k in model_state and v.shape == model_state[k].shape:
                    model_state[k] = v
                    transferred += 1
            self.model.load_state_dict(model_state)
            print(f'Transferred {transferred} layer weights successfully.')
        self.criterion = CombinedOpenSetLoss(in_features=512, num_classes=self.num_classes, w_triplet=1.0, w_ortho=0.1, arcface_margin=0.35, triplet_margin=0.3).to(self.device)
        params = list(self.model.parameters()) + list(self.criterion.parameters())
        self.optimizer = torch.optim.AdamW(params, lr=lr, weight_decay=weight_decay)
        self.scaler = torch.amp.GradScaler('cuda') if self.device.type == 'cuda' else None
        self.history = []

    def _get_lr(self, epoch: int) -> float:
        if epoch < self.warmup_epochs:
            return self.base_lr * (epoch + 1) / self.warmup_epochs
        progress = (epoch - self.warmup_epochs) / max(1, self.num_epochs - self.warmup_epochs)
        return self.base_lr * 0.5 * (1.0 + math.cos(math.pi * progress))

    def train_epoch(self, epoch: int) -> Dict[str, float]:
        self.model.train()
        self.criterion.train()
        current_lr = self._get_lr(epoch)
        for pg in self.optimizer.param_groups:
            pg['lr'] = current_lr
        epoch_losses = {'loss_total': 0.0, 'loss_arcface': 0.0, 'loss_triplet': 0.0, 'loss_ortho': 0.0}
        num_batches = 0
        for images, labels, _, _ in self.train_loader:
            images = images.to(self.device)
            labels = labels.to(self.device)
            self.optimizer.zero_grad()
            if self.scaler is not None:
                with torch.amp.autocast('cuda'):
                    embeddings, aux = self.model(images)
                    loss, loss_dict = self.criterion(embeddings, labels, aux)
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                embeddings, aux = self.model(images)
                loss, loss_dict = self.criterion(embeddings, labels, aux)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
                self.optimizer.step()
            for k in epoch_losses:
                epoch_losses[k] += loss_dict.get(k, 0.0)
            num_batches += 1
        if num_batches > 0:
            for k in epoch_losses:
                epoch_losses[k] /= num_batches
        epoch_losses['lr'] = current_lr
        epoch_losses['epoch'] = epoch + 1
        return epoch_losses

    def run(self) -> str:
        print(f'\nStarting Market-1501 Training on {self.device} | {len(self.train_loader)} batches/epoch...')
        start_time = time.time()
        best_loss = float('inf')
        best_ckpt = None
        for ep in range(self.num_epochs):
            t_ep0 = time.time()
            losses = self.train_epoch(ep)
            ep_time = time.time() - t_ep0
            self.history.append(losses)
            print(f"Epoch [{ep + 1:02d}/{self.num_epochs:02d}] Total Loss: {losses['loss_total']:.4f} | ArcFace: {losses['loss_arcface']:.4f} | Triplet: {losses['loss_triplet']:.4f} | LR: {losses['lr']:.6f} | Time: {ep_time:.1f}s")
            if losses['loss_total'] < best_loss:
                best_loss = losses['loss_total']
                best_ckpt = os.path.join(self.output_dir, 'openset_reid_checkpoint.pth')
                torch.save({'model_state_dict': self.model.state_dict(), 'num_classes': self.num_classes, 'history': self.history}, best_ckpt)
        total_time = time.time() - start_time
        print(f'\n✅ Training Completed in {total_time:.2f}s (~{total_time / 60:.1f} min)')
        print(f'Best Model Checkpoint: {best_ckpt}')
        return best_ckpt
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--market-dir', type=str, default='D:\\zed digital\\Market-1501-v15.09.15\\Market-1501-v15.09.15')
    parser.add_argument('--pretrained', type=str, default='experiments/best_model.pth')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--lr', type=float, default=0.00035)
    parser.add_argument('--output-dir', type=str, default='experiments/market1501_updated')
    args = parser.parse_args()
    trainer = Market1501Trainer(market_dir=args.market_dir, pretrained_ckpt=args.pretrained, output_dir=args.output_dir, num_epochs=args.epochs, lr=args.lr)
    trainer.run()
