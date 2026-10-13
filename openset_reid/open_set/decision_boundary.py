"""
Open-Set Decision Boundary Formulation and Rejection Rules.
Implements:
1. Nearest-Neighbor Contrast Ratio (NNCR / Multi-Gallery Margin)
2. Multi-Criterion Decision Boundary (Score + Margin + EVT)
3. Operating Point Calibration for Target Recall / Fixed FAR
"""

import numpy as np
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass


@dataclass
class MatchDecision:
    """Detailed matching result for a single probe query."""
    is_accepted: bool
    matched_identity: Optional[str]
    confidence: float
    raw_score: float
    contrast_margin: float
    second_identity: Optional[str]
    rejection_reason: Optional[str]
    evt_tail_score: float


class OpenSetDecisionEngine:
    """
    Evaluates probe queries against an enrolled gallery using a calibrated
    multi-criterion boundary designed to suppress false accepts in uniform environments.
    """
    def __init__(self,
                 score_threshold: float = 0.65,
                 margin_threshold: float = 0.06,
                 evt_threshold: float = 0.50,
                 use_contrast_margin: bool = True,
                 use_evt: bool = True):
        self.score_threshold = score_threshold
        self.margin_threshold = margin_threshold
        self.evt_threshold = evt_threshold
        self.use_contrast_margin = use_contrast_margin
        self.use_evt = use_evt

    def evaluate_match(self,
                       gallery_ids: List[str],
                       scores: np.ndarray,
                       calibrated_confidence: float,
                       evt_tail_score: float = 1.0) -> MatchDecision:
        """
        Evaluates a probe against candidate scores.
        
        Args:
            gallery_ids: Identity string of each gallery item [N]
            scores: Array of similarity scores to each gallery item [N]
            calibrated_confidence: Post-calibration confidence [0, 1]
            evt_tail_score: EVT confidence [0, 1] (high = not an impostor)
        """
        if len(scores) == 0:
            return MatchDecision(
                is_accepted=False,
                matched_identity=None,
                confidence=0.0,
                raw_score=0.0,
                contrast_margin=0.0,
                second_identity=None,
                rejection_reason="Empty gallery",
                evt_tail_score=0.0
            )

        # Sort candidate scores descending
        sorted_indices = np.argsort(scores)[::-1]
        top_idx = sorted_indices[0]
        top_score = float(scores[top_idx])
        top_id = gallery_ids[top_idx]

        # Find second-best score from a DIFFERENT identity
        second_id = None
        second_score = -1.0
        for idx in sorted_indices[1:]:
            cand_id = gallery_ids[idx]
            if cand_id != top_id:
                second_id = cand_id
                second_score = float(scores[idx])
                break

        # If gallery only contains one identity, margin is distance to zero baseline
        contrast_margin = top_score - second_score if second_id is not None else top_score

        # Multi-criterion decision logic
        # 1. Primary score check
        if top_score < self.score_threshold:
            return MatchDecision(
                is_accepted=False,
                matched_identity=None,
                confidence=calibrated_confidence,
                raw_score=top_score,
                contrast_margin=contrast_margin,
                second_identity=second_id,
                rejection_reason=f"Score below threshold ({top_score:.3f} < {self.score_threshold:.3f})",
                evt_tail_score=evt_tail_score
            )

        # 2. Contrast margin check (crucial for uniform sets)
        if self.use_contrast_margin and second_id is not None:
            if contrast_margin < self.margin_threshold:
                return MatchDecision(
                    is_accepted=False,
                    matched_identity=None,
                    confidence=calibrated_confidence,
                    raw_score=top_score,
                    contrast_margin=contrast_margin,
                    second_identity=second_id,
                    rejection_reason=f"Ambiguous uniform match / insufficient margin ({contrast_margin:.3f} < {self.margin_threshold:.3f})",
                    evt_tail_score=evt_tail_score
                )

        # 3. EVT tail check
        if self.use_evt and evt_tail_score < self.evt_threshold:
            return MatchDecision(
                is_accepted=False,
                matched_identity=None,
                confidence=calibrated_confidence,
                raw_score=top_score,
                contrast_margin=contrast_margin,
                second_identity=second_id,
                rejection_reason=f"Rejected by Extreme Value Theory (EVT score {evt_tail_score:.3f} < {self.evt_threshold:.3f})",
                evt_tail_score=evt_tail_score
            )

        # Passed all decision boundary tests -> Genuine Enrolled Match
        return MatchDecision(
            is_accepted=True,
            matched_identity=top_id,
            confidence=calibrated_confidence,
            raw_score=top_score,
            contrast_margin=contrast_margin,
            second_identity=second_id,
            rejection_reason=None,
            evt_tail_score=evt_tail_score
        )
