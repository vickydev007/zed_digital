import os
import time
import math
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Dict, Optional, Tuple
from openset_reid.models.openset_model import create_openset_model
from openset_reid.models.loss import CombinedOpenSetLoss
from openset_reid.data.dataset import ReIDImageDataset, PKRandomIdentitySampler
from openset_reid.training.config import TrainingConfig

class OpenSetTrainer:

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device = torch.device(config.device if torch.cuda.is_available() and config.device == 'cuda' else 'cpu')
        os.makedirs(config.output_dir, exist_ok=True)
        train_path = os.path.join(config.data_dir, 'train')
        self.train_dataset = ReIDImageDataset(train_path, is_train=True)
        self.num_classes = len(self.train_dataset.pid_dict)
        self.sampler = PKRandomIdentitySampler(self.train_dataset, p=config.p_identities, k=config.k_instances)
        self.train_loader = DataLoader(self.train_dataset, batch_size=config.p_identities * config.k_instances, sampler=self.sampler, num_workers=0, pin_memory=False, drop_last=True)
        self.model = create_openset_model(num_classes=self.num_classes, dual_granularity=config.use_dual_granularity, embedding_dim=config.embedding_dim).to(self.device)
        self.criterion = CombinedOpenSetLoss(in_features=config.embedding_dim, num_classes=self.num_classes, w_triplet=config.w_triplet, w_ortho=config.w_ortho, arcface_margin=config.arcface_margin, triplet_margin=config.triplet_margin).to(self.device)
        params = list(self.model.parameters()) + list(self.criterion.parameters())
        self.optimizer = torch.optim.AdamW(params, lr=config.lr, weight_decay=config.weight_decay)
        self.history = []

    def _get_lr(self, epoch: int, total_epochs: int) -> float:
        if epoch < self.config.warmup_epochs:
            return self.config.lr * (epoch + 1) / self.config.warmup_epochs
        progress = (epoch - self.config.warmup_epochs) / max(1, total_epochs - self.config.warmup_epochs)
        return self.config.lr * 0.5 * (1.0 + math.cos(math.pi * progress))

    def train_epoch(self, epoch: int) -> Dict[str, float]:
        self.model.train()
        self.criterion.train()
        current_lr = self._get_lr(epoch, self.config.num_epochs)
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = current_lr
        epoch_losses = {'loss_total': 0.0, 'loss_arcface': 0.0, 'loss_triplet': 0.0, 'loss_ortho': 0.0}
        num_batches = 0
        for images, labels, pids, paths in self.train_loader:
            images = images.to(self.device)
            labels = labels.to(self.device)
            self.optimizer.zero_grad()
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
        print(f'Starting training on device: {self.device} | Num classes: {self.num_classes} | Batches/epoch: {len(self.train_loader)}')
        start_time = time.time()
        for ep in range(self.config.num_epochs):
            losses = self.train_epoch(ep)
            self.history.append(losses)
            if (ep + 1) % 5 == 0 or ep == self.config.num_epochs - 1:
                print(f"Epoch [{ep + 1:02d}/{self.config.num_epochs:02d}] Total Loss: {losses['loss_total']:.4f} | ArcFace: {losses['loss_arcface']:.4f} | Triplet: {losses['loss_triplet']:.4f} | LR: {losses['lr']:.6f}")
        total_time = time.time() - start_time
        print(f'Training completed in {total_time:.2f}s')
        ckpt_path = os.path.join(self.config.output_dir, 'openset_reid_checkpoint.pth')
        torch.save({'model_state_dict': self.model.state_dict(), 'config': self.config, 'num_classes': self.num_classes, 'history': self.history}, ckpt_path)
        print(f'Checkpoint saved to {ckpt_path}')
        return ckpt_path
