from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class TrainingConfig:
    data_dir: str = 'd:/zed digital/data/low_variance_benchmark'
    output_dir: str = 'd:/zed digital/experiments'
    embedding_dim: int = 512
    use_dual_granularity: bool = True
    num_parts: int = 5
    base_channels: int = 64
    w_triplet: float = 1.0
    w_ortho: float = 0.1
    arcface_margin: float = 0.35
    triplet_margin: float = 0.3
    p_identities: int = 8
    k_instances: int = 4
    num_epochs: int = 15
    lr: float = 0.00035
    weight_decay: float = 0.0005
    warmup_epochs: int = 2
    score_threshold: float = 0.65
    margin_threshold: float = 0.05
    evt_tail_size: int = 25
    confidence_level: float = 0.99
    device: str = 'cpu'
    seed: int = 42
