import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional

class SubCenterArcFaceLoss(nn.Module):

    def __init__(self, in_features: int, num_classes: int, num_subcenters: int=2, scale: float=30.0, margin: float=0.35, easy_margin: bool=False):
        super().__init__()
        self.in_features = in_features
        self.num_classes = num_classes
        self.num_subcenters = num_subcenters
        self.scale = scale
        self.margin = margin
        self.easy_margin = easy_margin
        self.weight = nn.Parameter(torch.FloatTensor(num_classes * num_subcenters, in_features))
        nn.init.xavier_uniform_(self.weight)
        self.cos_m = math.cos(margin)
        self.sin_m = math.sin(margin)
        self.th = math.cos(math.pi - margin)
        self.mm = math.sin(math.pi - margin) * margin

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        norm_weight = F.normalize(self.weight, p=2, dim=1)
        cosine_all = F.linear(embeddings, norm_weight)
        B = embeddings.size(0)
        cosine_sub = cosine_all.view(B, self.num_classes, self.num_subcenters)
        cosine, _ = torch.max(cosine_sub, dim=-1)
        sine = torch.sqrt(1.0 - torch.clamp(cosine * cosine, 0.0, 1.0))
        phi = cosine * self.cos_m - sine * self.sin_m
        if self.easy_margin:
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1.0)
        logits = one_hot * phi + (1.0 - one_hot) * cosine
        logits = logits * self.scale
        loss = F.cross_entropy(logits, labels)
        return loss

class AdaptiveHardNegativeTripletLoss(nn.Module):

    def __init__(self, base_margin: float=0.3, adaptive_factor: float=0.2):
        super().__init__()
        self.base_margin = base_margin
        self.adaptive_factor = adaptive_factor

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor, global_features: Optional[torch.Tensor]=None) -> torch.Tensor:
        dist_mat = torch.cdist(embeddings, embeddings, p=2)
        B = embeddings.size(0)
        is_pos = labels.expand(B, B).eq(labels.expand(B, B).t())
        is_neg = labels.expand(B, B).ne(labels.expand(B, B).t())
        dist_ap = dist_mat * is_pos.float()
        hardest_dist_ap, _ = torch.max(dist_ap, dim=1)
        dist_an = dist_mat + (~is_neg).float() * 1000000.0
        hardest_dist_an, hardest_neg_idx = torch.min(dist_an, dim=1)
        if global_features is not None:
            global_sim = torch.mm(global_features, global_features.t())
            neg_sim = global_sim.gather(1, hardest_neg_idx.unsqueeze(1)).squeeze(1)
            dynamic_margin = self.base_margin + self.adaptive_factor * torch.clamp(neg_sim, min=0.0)
        else:
            dynamic_margin = self.base_margin
        loss = F.relu(hardest_dist_ap - hardest_dist_an + dynamic_margin)
        return loss.mean()

class PartOrthogonalityLoss(nn.Module):

    def __init__(self):
        super().__init__()

    def forward(self, part_weights: torch.Tensor) -> torch.Tensor:
        mean_weights = part_weights.mean(dim=0)
        entropy = -torch.sum(mean_weights * torch.log(mean_weights + 1e-08))
        uniform_entropy = math.log(part_weights.size(1))
        loss = (uniform_entropy - entropy).clamp(min=0.0)
        return loss

class CombinedOpenSetLoss(nn.Module):

    def __init__(self, in_features: int, num_classes: int, w_triplet: float=1.0, w_ortho: float=0.1, arcface_margin: float=0.35, triplet_margin: float=0.3):
        super().__init__()
        self.w_triplet = w_triplet
        self.w_ortho = w_ortho
        self.arcface = SubCenterArcFaceLoss(in_features=in_features, num_classes=num_classes, margin=arcface_margin)
        self.triplet = AdaptiveHardNegativeTripletLoss(base_margin=triplet_margin, adaptive_factor=0.25)
        self.part_ortho = PartOrthogonalityLoss()

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor, aux_outputs: Optional[Dict[str, torch.Tensor]]=None) -> Tuple[torch.Tensor, Dict[str, float]]:
        loss_arc = self.arcface(embeddings, labels)
        global_feats = aux_outputs.get('f_global', None) if aux_outputs else None
        loss_trip = self.triplet(embeddings, labels, global_features=global_feats)
        loss_ortho = torch.tensor(0.0, device=embeddings.device)
        if aux_outputs and 'part_weights' in aux_outputs:
            loss_ortho = self.part_ortho(aux_outputs['part_weights'])
        total_loss = loss_arc + self.w_triplet * loss_trip + self.w_ortho * loss_ortho
        loss_dict = {'loss_total': total_loss.item(), 'loss_arcface': loss_arc.item(), 'loss_triplet': loss_trip.item(), 'loss_ortho': loss_ortho.item()}
        return (total_loss, loss_dict)
