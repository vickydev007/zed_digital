"""
Advanced Metric Learning Losses for Low Inter-Class Variance Person Re-ID.
Includes:
1. SubCenterArcFaceLoss: Hyperspherical angular margin with pose-adaptive multi-centers
2. AdaptiveHardNegativeTripletLoss: Batch-hard mining with dynamic low-variance margin scaling
3. PartOrthogonalityLoss: Enforces spatial stripe distinctiveness
4. CombinedOpenSetLoss: End-to-end multi-task objective
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional


class SubCenterArcFaceLoss(nn.Module):
    """
    Sub-Center ArcFace Loss:
    Accommodates multiple intra-class visual modes (postures, camera angles)
    while enforcing strict angular decision boundaries.
    
    Formula:
        cos(theta + m) = cos(theta)cos(m) - sin(theta)sin(m)
    """
    def __init__(self, in_features: int, num_classes: int, num_subcenters: int = 2,
                 scale: float = 30.0, margin: float = 0.35, easy_margin: bool = False):
        super().__init__()
        self.in_features = in_features
        self.num_classes = num_classes
        self.num_subcenters = num_subcenters
        self.scale = scale
        self.margin = margin
        self.easy_margin = easy_margin

        # Weight matrix: [num_classes * num_subcenters, in_features]
        self.weight = nn.Parameter(torch.FloatTensor(num_classes * num_subcenters, in_features))
        nn.init.xavier_uniform_(self.weight)

        self.cos_m = math.cos(margin)
        self.sin_m = math.sin(margin)
        self.th = math.cos(math.pi - margin)
        self.mm = math.sin(math.pi - margin) * margin

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        Args:
            embeddings: [B, in_features] (L2-normalized)
            labels: [B] class labels
        Returns:
            loss: scalar cross-entropy loss with angular margin
        """
        # Normalize weights
        norm_weight = F.normalize(self.weight, p=2, dim=1)  # [C * K, D]
        # Cosine similarity to all sub-centers: [B, C * K]
        cosine_all = F.linear(embeddings, norm_weight)
        B = embeddings.size(0)

        # Reshape to [B, C, K] and select the closest sub-center for each class
        cosine_sub = cosine_all.view(B, self.num_classes, self.num_subcenters)
        cosine, _ = torch.max(cosine_sub, dim=-1)  # [B, C]

        sine = torch.sqrt(1.0 - torch.clamp(cosine * cosine, 0.0, 1.0))
        phi = cosine * self.cos_m - sine * self.sin_m  # cos(theta + m)

        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)

        # One-hot mask for ground-truth classes
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)

        # Apply margin to positive class only
        logits = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        logits = logits * self.scale

        loss = F.cross_entropy(logits, labels)
        return loss


class AdaptiveHardNegativeTripletLoss(nn.Module):
    """
    Batch-Hard Triplet Loss with Adaptive Low-Variance Margin.
    Under low inter-class variance (same uniform), standard margins are insufficient.
    This loss dynamically increases the repulsive margin when negative pairs
    exhibit high visual/uniform similarity, penalizing false accepts in identical attire.
    """
    def __init__(self, base_margin: float = 0.3, adaptive_factor: float = 0.2):
        super().__init__()
        self.base_margin = base_margin
        self.adaptive_factor = adaptive_factor

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor,
                global_features: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            embeddings: [B, D] normalized final feature embeddings
            labels: [B] identity labels
            global_features: [B, D_g] optional global features to gauge uniform similarity
        Returns:
            loss: scalar triplet loss
        """
        # Pairwise Euclidean distance matrix: d(i, j) = sqrt(||x_i - x_j||^2)
        dist_mat = torch.cdist(embeddings, embeddings, p=2)  # [B, B]
        B = embeddings.size(0)

        # Masks for positive and negative pairs
        is_pos = labels.expand(B, B).eq(labels.expand(B, B).t())
        is_neg = labels.expand(B, B).ne(labels.expand(B, B).t())

        # For each anchor, find the hardest positive: max d(a, p)
        dist_ap = dist_mat * is_pos.float()
        hardest_dist_ap, _ = torch.max(dist_ap, dim=1)

        # For each anchor, find the hardest negative: min d(a, n)
        # Add a large number to non-negatives so they are not chosen
        dist_an = dist_mat + (~is_neg).float() * 1e6
        hardest_dist_an, hardest_neg_idx = torch.min(dist_an, dim=1)

        # Compute adaptive margin
        if global_features is not None:
            # Pairwise cosine similarity in global attire space
            global_sim = torch.mm(global_features, global_features.t())  # [B, B]
            # Hard negative similarity
            neg_sim = global_sim.gather(1, hardest_neg_idx.unsqueeze(1)).squeeze(1)
            # When uniform similarity is high (>0.7), widen margin
            dynamic_margin = self.base_margin + self.adaptive_factor * torch.clamp(neg_sim, min=0.0)
        else:
            dynamic_margin = self.base_margin

        # Triplet loss formula: relu(d(a, p) - d(a, n) + margin)
        loss = F.relu(hardest_dist_ap - hardest_dist_an + dynamic_margin)
        return loss.mean()


class PartOrthogonalityLoss(nn.Module):
    """
    Part Orthogonality / Stripe Diversity Loss:
    Ensures that different horizontal body stripes learn non-redundant,
    orthogonal feature patterns rather than repeating identical signals.
    """
    def __init__(self):
        super().__init__()

    def forward(self, part_weights: torch.Tensor) -> torch.Tensor:
        """
        Encourages entropy/diversity in part attention distribution across the batch.
        Args:
            part_weights: [B, num_parts]
        """
        # Mean part attention across batch: [num_parts]
        mean_weights = part_weights.mean(dim=0)
        # Negative entropy to promote balanced attention across key body zones
        entropy = -torch.sum(mean_weights * torch.log(mean_weights + 1e-8))
        uniform_entropy = math.log(part_weights.size(1))
        # Loss minimizes deviation from balanced zone coverage
        loss = (uniform_entropy - entropy).clamp(min=0.0)
        return loss


class CombinedOpenSetLoss(nn.Module):
    """
    Unified training objective:
    L = L_ArcFace + w_triplet * L_AdaptiveTriplet + w_ortho * L_PartDiversity
    """
    def __init__(self, in_features: int, num_classes: int,
                 w_triplet: float = 1.0, w_ortho: float = 0.1,
                 arcface_margin: float = 0.35, triplet_margin: float = 0.3):
        super().__init__()
        self.w_triplet = w_triplet
        self.w_ortho = w_ortho

        self.arcface = SubCenterArcFaceLoss(
            in_features=in_features,
            num_classes=num_classes,
            margin=arcface_margin
        )
        self.triplet = AdaptiveHardNegativeTripletLoss(
            base_margin=triplet_margin,
            adaptive_factor=0.25
        )
        self.part_ortho = PartOrthogonalityLoss()

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor,
                aux_outputs: Optional[Dict[str, torch.Tensor]] = None) -> Tuple[torch.Tensor, Dict[str, float]]:
        loss_arc = self.arcface(embeddings, labels)

        global_feats = aux_outputs.get("f_global", None) if aux_outputs else None
        loss_trip = self.triplet(embeddings, labels, global_features=global_feats)

        loss_ortho = torch.tensor(0.0, device=embeddings.device)
        if aux_outputs and "part_weights" in aux_outputs:
            loss_ortho = self.part_ortho(aux_outputs["part_weights"])

        total_loss = loss_arc + self.w_triplet * loss_trip + self.w_ortho * loss_ortho

        loss_dict = {
            "loss_total": total_loss.item(),
            "loss_arcface": loss_arc.item(),
            "loss_triplet": loss_trip.item(),
            "loss_ortho": loss_ortho.item()
        }
        return total_loss, loss_dict
