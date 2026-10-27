import os
import sys
import time
import json
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Callable
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from openset_reid.deployment.onnx_inference import ONNXReIDEngine
from openset_reid.open_set.calibrator import OpenSetMatcher
from openset_reid.sensors.camera_profiles import get_camera_profile, CameraSensorProfile

try:
    import torch
    import torchvision
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

class IdentityStatus(str, Enum):
    OFFICIAL_WORKER = 'OFFICIAL_WORKER'
    NEW_CANDIDATE = 'NEW_CANDIDATE'
    UNKNOWN = 'UNKNOWN'

class PassageStatus(str, Enum):
    FIRST_ENTRY = 'FIRST_ENTRY'
    PASSAGE_IN_PROGRESS = 'PASSAGE_IN_PROGRESS'
    ALREADY_PASSED = 'ALREADY_PASSED'
    REPEAT_PASSAGE = 'REPEAT_PASSAGE'

class PersonCategory(str, Enum):
    OFFICIAL_WORKER = 'OFFICIAL_WORKER'
    NEW_PERSON = 'NEW_PERSON'
    PREVIOUSLY_ENROLLED = 'PREVIOUSLY_ENROLLED'
    UNKNOWN = 'UNKNOWN'

def resolve_display_category(identity_status: IdentityStatus, passage_status: PassageStatus) -> PersonCategory:
    if passage_status == PassageStatus.REPEAT_PASSAGE:
        return PersonCategory.PREVIOUSLY_ENROLLED
    if identity_status == IdentityStatus.OFFICIAL_WORKER:
        return PersonCategory.OFFICIAL_WORKER
    if identity_status == IdentityStatus.NEW_CANDIDATE:
        return PersonCategory.NEW_PERSON
    return PersonCategory.UNKNOWN

CATEGORY_COLORS_BGR = {
    PersonCategory.OFFICIAL_WORKER: (108, 207, 68),
    PersonCategory.NEW_PERSON: (240, 160, 46),
    PersonCategory.PREVIOUSLY_ENROLLED: (35, 166, 245),
    PersonCategory.UNKNOWN: (69, 69, 232)
}

class OfflineVideoAnalyzer:

    def __init__(
        self,
        onnx_model_path: str = 'experiments/deployment/openset_reid_v5.onnx',
        score_threshold: float = 0.85,
        contrast_margin: float = 0.10,
        min_observations: int = 3,
        policy_id: str = 'POL-ALERTING-V1',
        quality_min_h: int = 28,
        quality_min_w: int = 12,
        quality_min_blur: float = 30.0,
        device: str = 'auto',
        camera_id: Optional[str] = None,
        camera_profile: Optional[CameraSensorProfile] = None
    ):
        self.onnx_model_path = onnx_model_path
        self.score_threshold = float(score_threshold)
        self.contrast_margin = float(contrast_margin)
        self.min_observations = int(min_observations)
        self.policy_id = str(policy_id)
        self.quality_min_h = int(quality_min_h)
        self.quality_min_w = int(quality_min_w)
        self.quality_min_blur = float(quality_min_blur)
        self.camera_profile = camera_profile or get_camera_profile(camera_id)
        
        self.engine = ONNXReIDEngine(onnx_model_path)
        self.matcher = OpenSetMatcher(score_threshold=self.score_threshold, contrast_margin=self.contrast_margin)
        
        self.device = 'cpu'
        self.detector = None
        if TORCH_AVAILABLE:
            if device == 'auto':
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            else:
                self.device = device
            try:
                self.detector = torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn(weights='DEFAULT').to(self.device).eval()
            except Exception:
                self.detector = None

        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.active_tracks: List[Dict[str, Any]] = []
        self.finished_tracks: List[Dict[str, Any]] = []
        self.session_registry: Dict[int, Dict[str, Any]] = {}
        self.worker_passage_counts: Dict[str, int] = {}
        self.track_id_counter = 0
        self.candidate_id_counter = 0

    def enroll_worker(self, worker_id: str, person_crop_bgr: np.ndarray) -> bool:
        try:
            emb = self.engine.extract_embedding(person_crop_bgr)
            self.matcher.enroll(worker_id, emb)
            return True
        except Exception:
            return False

    def enroll_from_directory(self, gallery_dir: str) -> int:
        if not os.path.isdir(gallery_dir):
            return 0
        supported = {'.jpg', '.jpeg', '.png', '.bmp'}
        count = 0
        for fname in os.listdir(gallery_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext in supported:
                parts = os.path.splitext(fname)[0].split('_')
                worker_id = '_'.join(parts[:2]) if len(parts) >= 2 else parts[0]
                img_path = os.path.join(gallery_dir, fname)
                bgr = cv2.imread(img_path)
                if bgr is not None:
                    if self.enroll_worker(worker_id, bgr):
                        count += 1
        return count

    def assess_crop_quality(self, crop_bgr: np.ndarray) -> Tuple[bool, float, float]:
        h, w = crop_bgr.shape[:2]
        if h < self.quality_min_h or w < self.quality_min_w:
            return False, 0.0, 0.0
        aspect = h / max(1, w)
        if aspect < 1.0 or aspect > 4.5:
            return False, 0.0, 0.0
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_ok = (h >= self.quality_min_h and w >= self.quality_min_w and blur_var >= self.quality_min_blur)
        norm_res = min(1.0, (h * w) / (128.0 * 256.0))
        norm_sharp = min(1.0, blur_var / 250.0)
        quality_score = 0.5 * norm_res + 0.5 * norm_sharp
        return is_ok, blur_var, quality_score

    def detect_people(self, frame_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        h, w = frame_bgr.shape[:2]
        boxes: List[Tuple[int, int, int, int]] = []
        if self.detector is not None:
            det_w, det_h = 640, 360
            small = cv2.resize(frame_bgr, (det_w, det_h), interpolation=cv2.INTER_LINEAR)
            small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            t_uint8 = torch.from_numpy(small_rgb).to(self.device, non_blocking=True)
            tensor = t_uint8.permute(2, 0, 1).float().div_(255.0).unsqueeze(0)
            with torch.no_grad():
                preds = self.detector(tensor)[0]
            mask = (preds['labels'] == 1) & (preds['scores'] > 0.52)
            raw_boxes = preds['boxes'][mask].cpu().numpy()
            scale_x = w / float(det_w)
            scale_y = h / float(det_h)
            for rb in raw_boxes:
                x1 = max(0, int(rb[0] * scale_x))
                y1 = max(0, int(rb[1] * scale_y))
                x2 = min(w, int(rb[2] * scale_x))
                y2 = min(h, int(rb[3] * scale_y))
                bw = x2 - x1
                bh = y2 - y1
                aspect = bh / max(1, bw)
                if bh >= self.quality_min_h and bw >= self.quality_min_w and 1.0 <= aspect <= 4.5:
                    boxes.append((x1, y1, bw, bh))
            return boxes

        fg = self.bg_subtractor.apply(frame_bgr)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 250:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bh / max(1, bw)
                if 1.1 <= aspect <= 4.2 and bh >= self.quality_min_h and bw >= self.quality_min_w and bh <= int(h * 0.65):
                    boxes.append((bx, by, bw, bh))
        return boxes

    def match_embedding_to_gallery(self, embedding: np.ndarray) -> Tuple[IdentityStatus, Optional[str], float, float, float, Optional[str]]:
        if self.matcher.gallery_size == 0:
            return IdentityStatus.UNKNOWN, None, 0.0, 0.0, 0.0, 'Empty enrolled gallery'

        dec = self.matcher.match(embedding)
        s1 = float(dec.raw_score)
        margin = float(dec.contrast_margin)
        s2 = s1 - margin
        
        if dec.is_accepted:
            return IdentityStatus.OFFICIAL_WORKER, dec.matched_identity, s1, s2, margin, None
        else:
            return IdentityStatus.UNKNOWN, dec.matched_identity, s1, s2, margin, dec.rejection_reason

    def update_tracks(self, frame_bgr: np.ndarray, frame_rgb: Any = None, detected_boxes: Any = None, frame_idx: int = 0):
        if isinstance(frame_rgb, list) and (detected_boxes is None or isinstance(detected_boxes, int)):
            frame_idx = detected_boxes if isinstance(detected_boxes, int) else 0
            boxes_to_use = frame_rgb
        elif isinstance(detected_boxes, list):
            boxes_to_use = detected_boxes
        else:
            boxes_to_use = []

        h, w = frame_bgr.shape[:2]
        updated: List[Dict[str, Any]] = []
        unmatched = list(boxes_to_use)

        for trk in self.active_tracks:
            tx1, ty1, tbw, tbh = trk['box']
            tx2, ty2 = tx1 + tbw, ty1 + tbh
            best_iou = 0.0
            best_idx = -1
            for idx, (dx1, dy1, dbw, dbh) in enumerate(unmatched):
                dx2, dy2 = dx1 + dbw, dy1 + dbh
                ix1, iy1 = max(tx1, dx1), max(ty1, dy1)
                ix2, iy2 = min(tx2, dx2), min(ty2, dy2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = (tbw * tbh) + (dbw * dbh) - inter
                iou = inter / max(1.0, union)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_iou > 0.28 and best_idx >= 0:
                det = unmatched.pop(best_idx)
                trk['box'] = det
                trk['lost'] = 0
                trk['seen_frames'] += 1
                trk['last_frame'] = frame_idx
                
                if trk['seen_frames'] >= 25 and trk['passage_status'] == PassageStatus.PASSAGE_IN_PROGRESS:
                    trk['passage_status'] = PassageStatus.ALREADY_PASSED
                elif trk['seen_frames'] >= 10 and trk['passage_status'] == PassageStatus.FIRST_ENTRY:
                    trk['passage_status'] = PassageStatus.PASSAGE_IN_PROGRESS

                x, y, bw, bh = det
                crop_bgr = frame_bgr[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)]
                if crop_bgr.shape[0] >= self.quality_min_h and crop_bgr.shape[1] >= self.quality_min_w:
                    q_ok, blur_v, q_score = self.assess_crop_quality(crop_bgr)
                    if q_score > trk['best_quality']:
                        trk['best_quality'] = q_score
                        trk['representative_crop'] = crop_bgr.copy()
                        trk['representative_blur'] = blur_v

                trk['frames_since_reid'] += 1
                if trk['frames_since_reid'] >= 5 and crop_bgr.shape[0] >= self.quality_min_h:
                    q_ok, _, q_score = self.assess_crop_quality(crop_bgr)
                    if q_ok:
                        try:
                            crop_corr = self.camera_profile.apply_to_crop(crop_bgr)
                            emb = self.engine.extract_embedding(crop_corr)
                            trk.setdefault('observation_embeddings', []).append(emb)
                            trk.setdefault('observation_qualities', []).append(q_score)
                            if len(trk['observation_embeddings']) > 15:
                                trk['observation_embeddings'].pop(0)
                                trk['observation_qualities'].pop(0)

                            obs_embs = trk['observation_embeddings']
                            obs_qs = np.array(trk['observation_qualities'], dtype=np.float32)
                            obs_qs /= max(float(np.sum(obs_qs)), 1e-6)
                            pooled_emb = np.sum([w * e for w, e in zip(obs_qs, obs_embs)], axis=0)
                            pooled_emb /= max(float(np.linalg.norm(pooled_emb)), 1e-6)

                            trk['embedding'] = pooled_emb
                            id_status, best_id, s1, s2, margin, reason = self.match_embedding_to_gallery(pooled_emb)
                            
                            if len(obs_embs) < self.min_observations and id_status == IdentityStatus.OFFICIAL_WORKER:
                                id_status = IdentityStatus.UNKNOWN
                                reason = f"Awaiting multi-frame consensus ({len(obs_embs)} < {self.min_observations} observations)"

                            if id_status == IdentityStatus.OFFICIAL_WORKER:
                                trk['identity_status'] = id_status
                                trk['matched_identity'] = best_id
                                trk['candidate_id'] = None
                            elif trk.get('identity_status') == IdentityStatus.OFFICIAL_WORKER and len(obs_embs) >= self.min_observations + 2:
                                pass
                            else:
                                trk['identity_status'] = id_status
                                trk['matched_identity'] = None
                            trk['best_score'] = s1
                            trk['runner_up_score'] = s2
                            trk['score_margin'] = margin
                            trk['rejection_reason'] = reason
                            trk['frames_since_reid'] = 0
                        except Exception:
                            pass

                updated.append(trk)
            else:
                trk['lost'] += 1
                if trk['lost'] <= 5:
                    updated.append(trk)
                else:
                    self.finished_tracks.append(trk)
                    if len(self.finished_tracks) > 100:
                        self.finished_tracks = self.finished_tracks[-50:]

        for dx1, dy1, dbw, dbh in unmatched:
            crop_bgr = frame_bgr[max(0, dy1):min(h, dy1 + dbh), max(0, dx1):min(w, dx1 + dbw)]
            if crop_bgr.shape[0] < self.quality_min_h or crop_bgr.shape[1] < self.quality_min_w:
                continue

            q_ok, blur_v, q_score = self.assess_crop_quality(crop_bgr)
            if not q_ok:
                continue
            try:
                crop_corr = self.camera_profile.apply_to_crop(crop_bgr)
                emb = self.engine.extract_embedding(crop_corr)
            except Exception:
                continue

            id_status, best_id, s1, s2, margin, reason = self.match_embedding_to_gallery(emb)
            
            self.track_id_counter += 1
            cur_track_id = self.track_id_counter

            if self.min_observations > 1 and id_status == IdentityStatus.OFFICIAL_WORKER:
                id_status = IdentityStatus.UNKNOWN
                reason = f"Awaiting multi-frame consensus (1 < {self.min_observations} observations)"

            if id_status == IdentityStatus.OFFICIAL_WORKER:
                prev_visits = self.worker_passage_counts.get(best_id, 0)
                if prev_visits == 0:
                    passage_st = PassageStatus.FIRST_ENTRY
                else:
                    passage_st = PassageStatus.REPEAT_PASSAGE
                self.worker_passage_counts[best_id] = prev_visits + 1
                candidate_id = None
            else:
                matched_registry_id = None
                for reg_id, reg_data in self.session_registry.items():
                    p_emb = reg_data['embedding']
                    sim = float(np.dot(emb, p_emb) / (np.linalg.norm(emb) * np.linalg.norm(p_emb) + 1e-08))
                    if sim > 0.70:
                        matched_registry_id = reg_id
                        reg_data['repeat_count'] += 1
                        break

                if matched_registry_id is not None:
                    passage_st = PassageStatus.REPEAT_PASSAGE
                    candidate_id = matched_registry_id
                else:
                    passage_st = PassageStatus.FIRST_ENTRY
                    if q_ok:
                        self.candidate_id_counter += 1
                        candidate_id = self.candidate_id_counter
                        id_status = IdentityStatus.NEW_CANDIDATE
                        reason = None
                    else:
                        candidate_id = None

                    self.session_registry[cur_track_id] = {
                        'track_id': cur_track_id,
                        'embedding': emb,
                        'repeat_count': 1,
                        'identity_status': id_status,
                        'matched_identity': None
                    }

            if not q_ok and id_status != IdentityStatus.OFFICIAL_WORKER:
                id_status = IdentityStatus.UNKNOWN
                reason = f'Low crop quality / blur ({blur_v:.1f} < {self.quality_min_blur:.1f})'

            updated.append({
                'track_id': cur_track_id,
                'candidate_id': candidate_id,
                'box': (dx1, dy1, dbw, dbh),
                'embedding': emb,
                'observation_embeddings': [emb],
                'observation_qualities': [q_score],
                'identity_status': id_status,
                'passage_status': passage_st,
                'matched_identity': best_id if id_status == IdentityStatus.OFFICIAL_WORKER else None,
                'best_score': s1,
                'runner_up_score': s2,
                'score_margin': margin,
                'rejection_reason': reason,
                'first_frame': frame_idx,
                'last_frame': frame_idx,
                'seen_frames': 1,
                'lost': 0,
                'frames_since_reid': 0,
                'representative_crop': crop_bgr.copy(),
                'representative_blur': blur_v,
                'best_quality': q_score
            })

        self.active_tracks = updated

    def render_hud_and_boxes(self, frame_bgr: np.ndarray, frame_idx: int, fps: float) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        
        counts = {
            PersonCategory.OFFICIAL_WORKER: 0,
            PersonCategory.NEW_PERSON: 0,
            PersonCategory.PREVIOUSLY_ENROLLED: 0,
            PersonCategory.UNKNOWN: 0
        }

        for trk in self.active_tracks:
            x, y, bw, bh = trk['box']
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(w, x + bw), min(h, y + bh)
            
            id_st = trk['identity_status']
            pass_st = trk['passage_status']
            category = resolve_display_category(id_st, pass_st)
            counts[category] += 1
            color = CATEGORY_COLORS_BGR[category]

            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, 2)
            corner_len = max(6, min(14, int(min(bw, bh) * 0.25)))
            cv2.line(frame_bgr, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y1), (x2 - corner_len, y1), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y1), (x2, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y2), (x1 + corner_len, y2), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y2), (x1, y2 - corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), 2)

            t_id = trk['track_id']
            if category == PersonCategory.OFFICIAL_WORKER:
                top_text = f'ID #{t_id:02d} | WORKER: {trk["matched_identity"]}'
            elif category == PersonCategory.PREVIOUSLY_ENROLLED:
                top_text = f'ID #{t_id:02d} | REPEAT PASSAGE'
            elif category == PersonCategory.NEW_PERSON:
                cand = trk.get('candidate_id') or t_id
                top_text = f'ID #{t_id:02d} | NEW PERSON #{cand:02d}'
            else:
                top_text = f'ID #{t_id:02d} | UNKNOWN'

            badge_w = max(80, min(180, int(len(top_text) * 7.2)))
            badge_h = 18
            badge_y1 = max(0, y1 - badge_h)
            badge_y2 = y1
            cv2.rectangle(frame_bgr, (x1, badge_y1), (x1 + badge_w, badge_y2), color, -1)
            cv2.putText(frame_bgr, top_text, (x1 + 4, badge_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.rectangle(frame_bgr, (0, 0), (w, 42), (15, 18, 30), -1)
        cv2.line(frame_bgr, (0, 42), (w, 42), (79, 110, 247), 1)
        
        hud_title = 'OFFLINE RE-ID PIPELINE | 4-CATEGORY PERSON MONITOR'
        hud_stats = f'Active: {len(self.active_tracks)} | Workers: {counts[PersonCategory.OFFICIAL_WORKER]} | Repeat: {counts[PersonCategory.PREVIOUSLY_ENROLLED]} | New: {counts[PersonCategory.NEW_PERSON]} | Unknown: {counts[PersonCategory.UNKNOWN]}'
        hud_meta = f'{self.policy_id} | tau={self.score_threshold:.2f} | k>={self.min_observations} | {fps:.1f} FPS'
        
        cv2.putText(frame_bgr, hud_title, (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (240, 244, 255), 1, cv2.LINE_AA)
        cv2.putText(frame_bgr, hud_stats, (int(w * 0.35), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (100, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(frame_bgr, hud_meta, (w - 240, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (68, 207, 108), 1, cv2.LINE_AA)

        return frame_bgr

    def analyze_video(self, video_path: str, output_video_path: Optional[str] = None, output_crops_dir: Optional[str] = None, output_json_path: Optional[str] = None, max_frames: Optional[int] = None, auto_enroll_lead_worker: bool = True, progress_callback: Optional[Callable[[int, int], None]] = None, is_cancelled_fn: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file '{video_path}' not found.")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file '{video_path}'.")

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if auto_enroll_lead_worker:
            ret_init, init_frame = cap.read()
            if ret_init:
                init_rgb = cv2.cvtColor(init_frame, cv2.COLOR_BGR2RGB)
                lead_crop = init_rgb[574:704, 255:312]
                if lead_crop.shape[0] > 20 and lead_crop.shape[1] > 10:
                    self.enroll_worker('Staff_Patrol', lead_crop)
            cap.release()
            cap = cv2.VideoCapture(video_path)

        writer = None
        if output_video_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_video_path, fourcc, fps_in, (w, h))

        if output_crops_dir:
            os.makedirs(output_crops_dir, exist_ok=True)

        t_start = time.time()
        fps_timer = time.time()
        frame_idx = 0
        fps = 0.0

        while True:
            if is_cancelled_fn and is_cancelled_fn():
                break
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            if frame_idx % 15 == 0:
                now = time.time()
                fps = 15.0 / max(1e-05, now - fps_timer)
                fps_timer = now

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if frame_idx % 2 == 1 or len(self.active_tracks) == 0:
                boxes = self.detect_people(frame)
                self.update_tracks(frame, frame_rgb, boxes, frame_idx)

            annotated_frame = self.render_hud_and_boxes(frame, frame_idx, fps)
            if writer:
                writer.write(annotated_frame)

            if progress_callback and (frame_idx % 10 == 0 or frame_idx == total_video_frames):
                try:
                    progress_callback(frame_idx, total_video_frames)
                except Exception:
                    pass

            if max_frames and frame_idx >= max_frames:
                break

        cap.release()
        if writer:
            writer.release()

        total_elapsed = time.time() - t_start
        all_tracks = self.finished_tracks + self.active_tracks

        for trk in all_tracks:
            t_id = trk['track_id']
            rep_crop = trk.get('representative_crop')
            category = resolve_display_category(trk['identity_status'], trk['passage_status'])
            if output_crops_dir and rep_crop is not None:
                crop_fname = f'track_{t_id:03d}_{category.value}.jpg'
                crop_path = os.path.join(output_crops_dir, crop_fname)
                cv2.imwrite(crop_path, rep_crop)
                trk['crop_file'] = crop_path
            else:
                trk['crop_file'] = None

        category_tallies = {
            PersonCategory.OFFICIAL_WORKER.value: 0,
            PersonCategory.NEW_PERSON.value: 0,
            PersonCategory.PREVIOUSLY_ENROLLED.value: 0,
            PersonCategory.UNKNOWN.value: 0
        }

        track_records = []
        for trk in all_tracks:
            cat = resolve_display_category(trk['identity_status'], trk['passage_status'])
            category_tallies[cat.value] += 1
            track_records.append({
                'track_id': trk['track_id'],
                'candidate_id': trk.get('candidate_id'),
                'identity_status': trk['identity_status'].value,
                'passage_status': trk['passage_status'].value,
                'display_category': cat.value,
                'matched_identity': trk.get('matched_identity'),
                'best_score': round(float(trk.get('best_score', 0.0)), 4),
                'runner_up_score': round(float(trk.get('runner_up_score', 0.0)), 4),
                'score_margin': round(float(trk.get('score_margin', 0.0)), 4),
                'rejection_reason': trk.get('rejection_reason'),
                'first_frame': trk['first_frame'],
                'last_frame': trk['last_frame'],
                'seen_frames': trk['seen_frames'],
                'crop_file': trk.get('crop_file')
            })

        summary = {
            'video_file': video_path,
            'output_video': output_video_path,
            'total_frames_processed': frame_idx,
            'video_resolution': [w, h],
            'elapsed_seconds': round(total_elapsed, 2),
            'average_fps': round(frame_idx / max(1e-05, total_elapsed), 2),
            'policy_id': self.policy_id,
            'threshold_tau': self.score_threshold,
            'contrast_margin': self.contrast_margin,
            'min_observations': self.min_observations,
            'total_tracks': len(all_tracks),
            'categories': category_tallies,
            'tracks': track_records
        }

        if output_json_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)

        return summary
