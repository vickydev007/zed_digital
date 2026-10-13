"""
Embedding Heads and Discriminative Part-Attentive Orthogonal Projection.
Engineered specifically to overcome uniform clothing dominance.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Optional


class GeneralizedMeanPoolingP(nn.Module):
    """
    Generalized Mean Pooling (GeM).
    f = (1/|X| sum(x^p))^(1/p)
    When p=1 -> Average Pooling.
    When p->inf -> Max Pooling.
    Learnable p allows the model to dynamically attend to salient fine-grained cues.
    """
    def __init__(self, p: float = 3.0, eps: float = 1e-6):
        super().__init__()
        self.p = nn.Parameter(torch.ones(1) * p)
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        p = self.p.clamp(min=1.0, max=10.0)
        x_clamp = x.clamp(min=self.eps)
        out = F.avg_pool2d(x_clamp.pow(p), (x.size(-2), x.size(-1))).pow(1.0 / p)
        return out


class HorizontalPartAttentivePooling(nn.Module):
    """
    Decomposes pedestrian feature maps into horizontal body stripes
    (Head/Hair, Upper Torso/Badge, Waist/Belt, Lower Torso/Pants, Feet/Shoes).
    Applies learnable channel-spatial cross-attention to each stripe.
    """
    def __init__(self, in_channels: int, num_parts: int = 5, part_dim: int = 128):
        super().__init__()
        self.num_parts = num_parts
        self.in_channels = in_channels
        self.part_dim = part_dim

        # Per-part projection and attention
        self.part_projections = nn.ModuleList([
            nn.Sequential(
                nn.Conv2d(in_channels, part_dim, kernel_size=1, bias=False),
                nn.BatchNorm2d(part_dim),
                nn.SiLU(inplace=True)
            ) for _ in range(num_parts)
        ])

        # Self-attention scoring for parts
        self.part_attention_scorer = nn.Sequential(
            nn.Linear(part_dim, 64),
            nn.SiLU(inplace=True),
            nn.Linear(64, 1)
        )

        self.fused_part_bn = nn.BatchNorm1d(part_dim)

    def forward(self, feat_map: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            feat_map: [B, C, H, W], e.g. [B, 384, 16, 8]
        Returns:
            fused_part_emb: [B, part_dim]
            part_weights: [B, num_parts]
        """
        B, C, H, W = feat_map.shape
        stripe_height = H // self.num_parts
        part_vectors = []

        for i in range(self.num_parts):
            start_h = i * stripe_height
            end_h = (i + 1) * stripe_height if i < self.num_parts - 1 else H
            stripe_feat = feat_map[:, :, start_h:end_h, :]  # [B, C, h_part, W]

            proj = self.part_projections[i](stripe_feat)  # [B, part_dim, h_part, W]
            pooled = F.adaptive_avg_pool2d(proj, 1).view(B, self.part_dim)  # [B, part_dim]
            part_vectors.append(pooled)

        stacked_parts = torch.stack(part_vectors, dim=1)  # [B, num_parts, part_dim]

        # Compute importance weights for each stripe (badges and shoes get higher weight in uniform sets)
        raw_scores = self.part_attention_scorer(stacked_parts).squeeze(-1)  # [B, num_parts]
        part_weights = F.softmax(raw_scores, dim=-1)  # [B, num_parts]

        # Weighted combination of fine-grained part vectors
        weighted_parts = (stacked_parts * part_weights.unsqueeze(-1)).sum(dim=1)  # [B, part_dim]
        fused_part_emb = self.fused_part_bn(weighted_parts)

        return fused_part_emb, part_weights


class OrthogonalProjectionLayer(nn.Module):
    """
    Orthogonal Subspace Projection:
    Projects the fine-grained part embedding f_part into the subspace orthogonal
    to the dominant global uniform embedding f_global.
    
    Mathematical Formulation:
        f_proj = (<f_part, f_global> / (||f_global||^2 + eps)) * f_global
        f_ortho = f_part - f_proj
    
    This explicitly removes the variance caused by shared clothing colors/silhouettes,
    isolating individual personal discriminators (ID badge, haircut, shoe type, wristwatch).
    """
    def __init__(self, eps: float = 1e-6):
        super().__init__()
        self.eps = eps

    def forward(self, f_part: torch.Tensor, f_global: torch.Tensor) -> torch.Tensor:
        """
        Args:
            f_part: [B, D]
            f_global: [B, D]
        Returns:
            f_ortho: [B, D]
        """
        # Ensure dimensions match
        dot = torch.sum(f_part * f_global, dim=1, keepdim=True)  # [B, 1]
        norm_sq = torch.sum(f_global * f_global, dim=1, keepdim=True).clamp(min=self.eps)  # [B, 1]
        f_proj = (dot / norm_sq) * f_global
        f_ortho = f_part - f_proj
        return f_ortho


class DualGranularityReIDHead(nn.Module):
    """
    Complete Dual-Granularity Re-ID Head:
    Combines:
    1. Global GeM feature branch (256-d) with BNNeck
    2. Horizontal Part-Attentive Stripe branch (128-d or 256-d)
    3. Orthogonal Subspace Filtering
    4. Learnable fusion and hyperspherical normalization
    """
    def __init__(self, in_channels: int = 384, global_dim: int = 256,
                 part_dim: int = 256, num_parts: int = 5):
        super().__init__()
        self.gem_pool = GeneralizedMeanPoolingP(p=3.0)
        self.global_fc = nn.Linear(in_channels, global_dim, bias=False)
        self.global_bn = nn.BatchNorm1d(global_dim)
        self.global_bn.bias.requires_grad_(False)  # BNNeck standard

        self.part_pool = HorizontalPartAttentivePooling(
            in_channels=in_channels,
            num_parts=num_parts,
            part_dim=part_dim
        )

        self.orthogonal_proj = OrthogonalProjectionLayer()
        self.part_scale = nn.Parameter(torch.tensor([1.2]))  # learnable emphasis on fine-grained cues

        self.total_dim = global_dim + part_dim

    def forward(self, feat_map: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            feat_map: [B, C, H, W]
        Returns:
            final_embedding: [B, total_dim] (L2-normalized)
            aux_outputs: dictionary containing intermediate representations
        """
        B = feat_map.size(0)

        # 1. Global GeM Branch
        pooled_global = self.gem_pool(feat_map).view(B, -1)
        f_global_raw = self.global_fc(pooled_global)
        f_global = self.global_bn(f_global_raw)

        # 2. Fine-Grained Part Branch
        f_part, part_weights = self.part_pool(feat_map)

        # 3. Orthogonal Projection to isolate uniform-independent cues
        f_ortho = self.orthogonal_proj(f_part, f_global)
        f_ortho = f_ortho * self.part_scale

        # 4. Fused Embedding
        f_fused = torch.cat([f_global, f_ortho], dim=1)  # [B, 512]
        norm_embedding = F.normalize(f_fused, p=2, dim=1)

        aux_outputs = {
            "f_global": F.normalize(f_global, p=2, dim=1),
            "f_part": F.normalize(f_part, p=2, dim=1),
            "f_ortho": F.normalize(f_ortho, p=2, dim=1),
            "part_weights": part_weights,
            "raw_global": f_global_raw
        }

        return norm_embedding, aux_outputs
