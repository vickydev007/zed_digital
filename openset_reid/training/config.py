"""
Configuration dataclasses for training, evaluation, and deployment.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class TrainingConfig:
    data_dir: str = "d:/zed digital/data/low_variance_benchmark"
    output_dir: str = "d:/zed digital/experiments"
    
    # Architecture
    embedding_dim: int = 512
    use_dual_granularity: bool = True
    num_parts: int = 5
    base_channels: int = 64
    
    # Loss Weights
    w_triplet: float = 1.0
    w_ortho: float = 0.1
    arcface_margin: float = 0.35
    triplet_margin: float = 0.30
    
    # Optimization
    p_identities: int = 8
    k_instances: int = 4
    num_epochs: int = 15
    lr: float = 3.5e-4
    weight_decay: float = 5e-4
    warmup_epochs: int = 2
    
    # Open-Set Calibration
    score_threshold: float = 0.65
    margin_threshold: float = 0.05
    evt_tail_size: int = 25
    confidence_level: float = 0.99
    
    device: str = "cpu"
    seed: int = 42
