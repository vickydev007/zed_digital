"""
Complete Open-Set Re-Identification Model Architecture.
Supports:
1. Full Dual-Granularity Embedding (Global + Orthogonal Part)
2. Fast Edge Single-Branch Mode for sub-10ms inference
3. Direct ONNX export compatibility
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional

from openset_reid.models.backbones import OmniScaleReIDBackbone
from openset_reid.models.heads import DualGranularityReIDHead


class OpenSetReIDModel(nn.Module):
    """
    Unified Open-Set Re-ID Architecture under Low Inter-Class Variance.
    """
    def __init__(self,
                 num_classes: Optional[int] = None,
                 base_channels: int = 64,
                 embedding_dim: int = 512,
                 num_parts: int = 5,
                 use_dual_granularity: bool = True):
        super().__init__()
        self.num_classes = num_classes
        self.use_dual_granularity = use_dual_granularity
        self.embedding_dim = embedding_dim

        # Backbone
        self.backbone = OmniScaleReIDBackbone(in_channels=3, base_channels=base_channels)
        backbone_dim = self.backbone.out_channels  # 384

        if use_dual_granularity:
            global_dim = embedding_dim // 2
            part_dim = embedding_dim - global_dim
            self.head = DualGranularityReIDHead(
                in_channels=backbone_dim,
                global_dim=global_dim,
                part_dim=part_dim,
                num_parts=num_parts
            )
        else:
            # Baseline single-branch head
            self.head = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Linear(backbone_dim, embedding_dim, bias=False),
                nn.BatchNorm1d(embedding_dim)
            )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        Inference extraction method: returns normalized embedding vector.
        Args:
            x: Pedestrian crop images [B, 3, 256, 128]
        Returns:
            embedding: [B, embedding_dim], unit L2 norm
        """
        feat_map = self.backbone(x)
        if self.use_dual_granularity:
            emb, _ = self.head(feat_map)
            return emb
        else:
            raw = self.head(feat_map)
            return F.normalize(raw, p=2, dim=1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[Dict[str, torch.Tensor]]]:
        """
        Training & Evaluation forward pass.
        """
        feat_map = self.backbone(x)
        if self.use_dual_granularity:
            emb, aux = self.head(feat_map)
            return emb, aux
        else:
            raw = self.head(feat_map)
            emb = F.normalize(raw, p=2, dim=1)
            return emb, {"raw_global": raw}


def create_openset_model(num_classes: Optional[int] = None,
                         dual_granularity: bool = True,
                         embedding_dim: int = 512) -> OpenSetReIDModel:
    """Factory helper function."""
    return OpenSetReIDModel(
        num_classes=num_classes,
        base_channels=64,
        embedding_dim=embedding_dim,
        num_parts=5,
        use_dual_granularity=dual_granularity
    )
