import numpy as np
from typing import Dict, Tuple, List, Optional, Union
from dataclasses import dataclass

@dataclass
class MatchDecision:
    is_accepted: bool
    matched_identity: Optional[str]
    confidence: float
    raw_score: float
    contrast_margin: float
    second_identity: Optional[str]
    rejection_reason: Optional[str]
    evt_tail_score: float

class OpenSetDecisionEngine:

    def __init__(self, score_threshold: float=0.65, margin_threshold: float=0.06, evt_threshold: float=0.5, contrast_margin: Optional[float]=None, use_contrast_margin: bool=True, use_evt: bool=True):
        if contrast_margin is not None:
            margin_threshold = contrast_margin
        self.score_threshold = score_threshold
        self.margin_threshold = margin_threshold
        self.evt_threshold = evt_threshold
        self.use_contrast_margin = use_contrast_margin
        self.use_evt = use_evt

    def evaluate_match(self, gallery_ids: List[str], scores: np.ndarray, calibrated_confidence: float, evt_tail_score: float=1.0) -> MatchDecision:
        if len(scores) == 0:
            return MatchDecision(is_accepted=False, matched_identity=None, confidence=0.0, raw_score=0.0, contrast_margin=0.0, second_identity=None, rejection_reason='Empty gallery', evt_tail_score=0.0)
        sorted_indices = np.argsort(scores)[::-1]
        top_idx = sorted_indices[0]
        top_score = float(scores[top_idx])
        top_id = gallery_ids[top_idx]
        second_id = None
        second_score = -1.0
        for idx in sorted_indices[1:]:
            cand_id = gallery_ids[idx]
            if cand_id != top_id:
                second_id = cand_id
                second_score = float(scores[idx])
                break
        contrast_margin = top_score - second_score if second_id is not None else top_score
        if top_score < self.score_threshold:
            return MatchDecision(is_accepted=False, matched_identity=None, confidence=calibrated_confidence, raw_score=top_score, contrast_margin=contrast_margin, second_identity=second_id, rejection_reason=f'Score below threshold ({top_score:.3f} < {self.score_threshold:.3f})', evt_tail_score=evt_tail_score)
        if self.use_contrast_margin and second_id is not None:
            if contrast_margin < self.margin_threshold:
                return MatchDecision(is_accepted=False, matched_identity=None, confidence=calibrated_confidence, raw_score=top_score, contrast_margin=contrast_margin, second_identity=second_id, rejection_reason=f'Ambiguous uniform match / insufficient margin ({contrast_margin:.3f} < {self.margin_threshold:.3f})', evt_tail_score=evt_tail_score)
        if self.use_evt and evt_tail_score < self.evt_threshold:
            return MatchDecision(is_accepted=False, matched_identity=None, confidence=calibrated_confidence, raw_score=top_score, contrast_margin=contrast_margin, second_identity=second_id, rejection_reason=f'Rejected by Extreme Value Theory (EVT score {evt_tail_score:.3f} < {self.evt_threshold:.3f})', evt_tail_score=evt_tail_score)
        return MatchDecision(is_accepted=True, matched_identity=top_id, confidence=calibrated_confidence, raw_score=top_score, contrast_margin=contrast_margin, second_identity=second_id, rejection_reason=None, evt_tail_score=evt_tail_score)
