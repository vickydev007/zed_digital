import os
import sys
import time
import argparse
from typing import Dict, List, Tuple, Optional
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openset_reid.deployment.onnx_inference import ONNXReIDEngine
from openset_reid.open_set.calibrator import OpenSetMatcher

try:
    import torch
    import torchvision
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

class RealtimeReIDPipeline:

    def __init__(self, onnx_model_path: str = 'experiments/deployment/openset_reid.onnx', score_threshold: float = 0.7124, contrast_margin: float = 0.05, evt_threshold: float = 0.4, mode: str = 'motion', detector: str = 'auto'):
        print(f'Loading ONNX Re-ID engine from {onnx_model_path}...')
        self.engine = ONNXReIDEngine(onnx_model_path)
        print(f'Configuring decision matcher: threshold={score_threshold:.4f}, margin={contrast_margin:.3f}...')
        self.matcher = OpenSetMatcher(score_threshold=score_threshold, contrast_margin=contrast_margin, evt_threshold=evt_threshold)
        self.mode = mode
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.active_tracks: List[Dict] = []
        self.passed_registry: Dict[int, np.ndarray] = {}
        self.track_id_counter = 0
        self.neural_detector = None
        self.device = 'cpu'
        
        if detector in ('auto', 'neural') and TORCH_AVAILABLE:
            try:
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
                print(f'Initializing FasterRCNN MobileNetV3 FPN pedestrian detector on {self.device.upper()}...')
                self.neural_detector = torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn(weights='DEFAULT').to(self.device).eval()
                print('Neural pedestrian detector initialized successfully.')
            except Exception as err:
                print(f'Could not load neural detector: {err}. Falling back to motion detector.')
                self.neural_detector = None

    def enroll_person(self, identity_name: str, person_crop: np.ndarray) -> bool:
        try:
            embedding = self.engine.extract_embedding(person_crop)
            self.matcher.enroll(identity_name, embedding)
            print(f"Enrolled '{identity_name}'. Total gallery count: {self.matcher.gallery_size}")
            return True
        except Exception as err:
            print(f'Failed to enroll {identity_name}: {err}')
            return False

    def enroll_from_directory(self, gallery_dir: str):
        if not os.path.isdir(gallery_dir):
            print(f"Gallery directory '{gallery_dir}' not found.")
            return
        supported_exts = {'.jpg', '.jpeg', '.png', '.bmp'}
        count = 0
        for fname in os.listdir(gallery_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext in supported_exts:
                parts = os.path.splitext(fname)[0].split('_')
                person_id = '_'.join(parts[:2]) if len(parts) >= 2 else parts[0]
                img_path = os.path.join(gallery_dir, fname)
                img = cv2.imread(img_path)
                if img is not None:
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    if self.enroll_person(person_id, img_rgb):
                        count += 1
        print(f'Pre-enrollment complete: {count} reference images loaded from {gallery_dir}.')

    def detect_candidate_regions(self, frame_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        h, w = frame_bgr.shape[:2]
        boxes: List[Tuple[int, int, int, int]] = []
        
        if self.mode == 'gate':
            box_h = int(h * 0.75)
            box_w = int(box_h * 0.5)
            cx = int((w - box_w) / 2)
            cy = int((h - box_h) / 2)
            boxes.append((cx, cy, box_w, box_h))
            return boxes

        if self.neural_detector is not None:
            det_w, det_h = 640, 360
            small = cv2.resize(frame_bgr, (det_w, det_h))
            small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            tensor = (torch.from_numpy(small_rgb).permute(2, 0, 1).float() / 255.0).unsqueeze(0).to(self.device)
            with torch.no_grad():
                preds = self.neural_detector(tensor)[0]
            scores = preds['scores'].cpu().numpy()
            labels = preds['labels'].cpu().numpy()
            raw_boxes = preds['boxes'].cpu().numpy()
            mask = (labels == 1) & (scores > 0.55)
            scale_x = w / float(det_w)
            scale_y = h / float(det_h)
            for rb in raw_boxes[mask]:
                x1 = max(0, int(rb[0] * scale_x))
                y1 = max(0, int(rb[1] * scale_y))
                x2 = min(w, int(rb[2] * scale_x))
                y2 = min(h, int(rb[3] * scale_y))
                bw = x2 - x1
                bh = y2 - y1
                aspect = bh / max(1, bw)
                if bh >= 28 and bw >= 12 and 1.0 <= aspect <= 4.5:
                    boxes.append((x1, y1, bw, bh))
            return boxes

        fg_mask = self.bg_subtractor.apply(frame_bgr)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 250:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bh / max(bw, 1)
                if 1.1 <= aspect <= 4.2 and 28 <= bh <= int(h * 0.65) and bw >= 12:
                    boxes.append((bx, by, bw, bh))
        return boxes

    def update_tracks(self, frame_rgb: np.ndarray, detected_boxes: List[Tuple[int, int, int, int]]):
        h, w = frame_rgb.shape[:2]
        updated_tracks: List[Dict] = []
        unmatched_detections = list(detected_boxes)

        for trk in self.active_tracks:
            tx1, ty1, tbw, tbh = trk['box']
            tx2, ty2 = tx1 + tbw, ty1 + tbh
            best_iou = 0.0
            best_det_idx = -1
            
            for idx, (dx1, dy1, dbw, dbh) in enumerate(unmatched_detections):
                dx2, dy2 = dx1 + dbw, dy1 + dbh
                ix1 = max(tx1, dx1)
                iy1 = max(ty1, dy1)
                ix2 = min(tx2, dx2)
                iy2 = min(ty2, dy2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = (tbw * tbh) + (dbw * dbh) - inter
                iou = inter / max(1.0, union)
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = idx
            
            if best_iou > 0.3 and best_det_idx >= 0:
                det = unmatched_detections.pop(best_det_idx)
                trk['box'] = det
                trk['lost'] = 0
                trk['seen_frames'] += 1
                
                if trk['seen_frames'] >= 10 and not trk['has_passed']:
                    trk['has_passed'] = True
                    self.passed_registry[trk['id']] = trk['embedding']
                
                trk['frames_since_reid'] += 1
                if trk['frames_since_reid'] >= 25:
                    x, y, bw, bh = det
                    crop = frame_rgb[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)]
                    if crop.shape[0] >= 20 and crop.shape[1] >= 12:
                        try:
                            emb = self.engine.extract_embedding(crop)
                            trk['embedding'] = emb
                            trk['decision'] = self.matcher.match(emb)
                            trk['frames_since_reid'] = 0
                        except Exception:
                            pass
                updated_tracks.append(trk)
            else:
                trk['lost'] += 1
                if trk['lost'] <= 4:
                    updated_tracks.append(trk)

        for dx1, dy1, dbw, dbh in unmatched_detections:
            crop = frame_rgb[max(0, dy1):min(h, dy1 + dbh), max(0, dx1):min(w, dx1 + dbw)]
            if crop.shape[0] >= 20 and crop.shape[1] >= 12:
                try:
                    emb = self.engine.extract_embedding(crop)
                    dec = self.matcher.match(emb)
                    
                    matched_passed_id = None
                    for pid, p_emb in self.passed_registry.items():
                        sim = float(np.dot(emb, p_emb) / (np.linalg.norm(emb) * np.linalg.norm(p_emb) + 1e-08))
                        if sim > 0.70:
                            matched_passed_id = pid
                            break
                            
                    if matched_passed_id is not None:
                        assigned_id = matched_passed_id
                        has_passed = True
                    else:
                        self.track_id_counter += 1
                        assigned_id = self.track_id_counter
                        has_passed = False

                    updated_tracks.append({
                        'id': assigned_id,
                        'box': (dx1, dy1, dbw, dbh),
                        'embedding': emb,
                        'decision': dec,
                        'has_passed': has_passed,
                        'seen_frames': 1,
                        'lost': 0,
                        'frames_since_reid': 0
                    })
                except Exception:
                    pass

        self.active_tracks = updated_tracks

    def process_frame(self, frame_bgr: np.ndarray, frame_idx: int) -> np.ndarray:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_bgr.shape[:2]
        
        if frame_idx % 2 == 0 or len(self.active_tracks) == 0:
            boxes = self.detect_candidate_regions(frame_bgr)
            self.update_tracks(frame_rgb, boxes)

        staff_count = 0
        passed_count = 0
        new_count = 0

        for trk in self.active_tracks:
            x, y, bw, bh = trk['box']
            dec = trk['decision']
            p_id = trk['id']
            has_passed = trk['has_passed']
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(w, x + bw), min(h, y + bh)
            
            if dec.is_accepted:
                staff_count += 1
                box_color = (68, 207, 108)
                status_text = f'ID #{p_id:02d} | STAFF [PASSED]'
            elif has_passed:
                passed_count += 1
                box_color = (240, 180, 50)
                status_text = f'ID #{p_id:02d} | ALREADY PASSED'
            else:
                new_count += 1
                box_color = (69, 110, 240)
                status_text = f'ID #{p_id:02d} | NEW'

            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), box_color, 2)
            corner_len = max(6, min(14, int(min(bw, bh) * 0.25)))
            cv2.line(frame_bgr, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y1), (x2 - corner_len, y1), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y1), (x2, y1 + corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y2), (x1 + corner_len, y2), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x1, y2), (x1, y2 - corner_len), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
            cv2.line(frame_bgr, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), 2)

            badge_w = max(80, min(175, int(len(status_text) * 7.2)))
            badge_h = 18
            badge_y1 = max(0, y1 - badge_h)
            badge_y2 = y1
            cv2.rectangle(frame_bgr, (x1, badge_y1), (x1 + badge_w, badge_y2), box_color, -1)
            cv2.putText(frame_bgr, status_text, (x1 + 4, badge_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.rectangle(frame_bgr, (0, 0), (w, 40), (15, 18, 30), -1)
        cv2.line(frame_bgr, (0, 40), (w, 40), (79, 110, 247), 1)
        hud_left = 'ZED DIGITAL | OPEN-SET RE-ID & PASSAGE MONITOR'
        hud_center = f'Tracked: {len(self.active_tracks)} | Already Passed: {passed_count} | New: {new_count} | Staff: {staff_count}'
        hud_right = f'tau: {self.matcher.decision_engine.score_threshold:.3f}'
        cv2.putText(frame_bgr, hud_left, (16, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (240, 244, 255), 1, cv2.LINE_AA)
        cv2.putText(frame_bgr, hud_center, (int(w * 0.42), 25), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(frame_bgr, hud_right, (w - 170, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (68, 207, 108), 1, cv2.LINE_AA)

        return frame_bgr

    def run_stream(self, source: str, max_frames: Optional[int] = None, output_video: Optional[str] = None, headless: bool = False, auto_enroll_lead: bool = True):
        if source.lower() == 'sample':
            source = 'data/sample_cctv.mp4'
        if source.isdigit():
            cap_src = int(source)
            src_desc = f'Webcam #{cap_src}'
        else:
            cap_src = source
            src_desc = f'Stream ({source})'
        print(f'Connecting to {src_desc}...')
        cap = cv2.VideoCapture(cap_src)
        if not cap.isOpened():
            print(f"Error: Could not open video source '{source}'.")
            return
        
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        in_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

        if auto_enroll_lead:
            ret_init, init_frame = cap.read()
            if ret_init:
                init_rgb = cv2.cvtColor(init_frame, cv2.COLOR_BGR2RGB)
                lead_crop = init_rgb[575:704, 263:314]
                if lead_crop.shape[0] > 20 and lead_crop.shape[1] > 10:
                    self.enroll_person('Staff_Patrol', lead_crop)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        writer = None
        if output_video:
            os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_video, fourcc, in_fps, (w, h))
            print(f'Writing annotated video to {output_video} ({w}x{h} @ {in_fps:.1f} FPS)...')

        print('-' * 65)
        print(f'  Live Open-Set Re-ID stream active on {src_desc}')
        print(f'  Mode: {self.mode.upper()} | Output: {output_video or "Screen"}')
        print('-' * 65)
        
        fps_timer = time.time()
        frame_count = 0
        fps = 0.0
        snapshot_saved = False

        while True:
            ret, frame = cap.read()
            if not ret:
                if max_frames is None and not str(source).isdigit() and os.path.exists(str(source)):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            
            frame_count += 1
            if frame_count % 15 == 0:
                now = time.time()
                fps = 15.0 / max(1e-05, now - fps_timer)
                fps_timer = now
                print(f'Processed {frame_count} frames | Current Throughput: {fps:.1f} FPS')
            
            annotated_frame = self.process_frame(frame, frame_count)
            cv2.putText(annotated_frame, f'{fps:.1f} FPS', (annotated_frame.shape[1] - 80, annotated_frame.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (68, 207, 108), 1, cv2.LINE_AA)
            
            if writer:
                writer.write(annotated_frame)
            
            if not snapshot_saved and frame_count >= 25:
                os.makedirs('experiments/reports', exist_ok=True)
                snapshot_path = 'experiments/reports/sample_cctv_reid_hud.jpg'
                cv2.imwrite(snapshot_path, annotated_frame)
                print(f'Snapshot saved to {snapshot_path}')
                snapshot_saved = True

            if not headless:
                cv2.imshow('Zed Digital — Open-Set Person Re-ID Stream', annotated_frame)
                key = cv2.waitKey(1) & 255
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    shot_name = f'reid_capture_{int(time.time())}.jpg'
                    cv2.imwrite(shot_name, annotated_frame)
                    print(f'Saved snapshot to {shot_name}')
                elif key == ord('m'):
                    self.mode = 'motion' if self.mode == 'gate' else 'gate'
                    print(f'Mode switched to: {self.mode.upper()}')

            if max_frames and frame_count >= max_frames:
                print(f'Reached target {max_frames} frames limit.')
                break

        cap.release()
        if writer:
            writer.release()
            print(f'Annotated video file saved: {output_video}')
        if not headless:
            cv2.destroyAllWindows()
        print(f'Stream stopped. Total frames processed: {frame_count}.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Real-Time Open-Set Person Re-ID Stream')
    parser.add_argument('--source', type=str, default='sample', help="Video source: '0' for webcam, 'rtsp://...' for IP camera, path to .mp4, or 'sample'")
    parser.add_argument('--onnx', type=str, default='experiments/deployment/openset_reid.onnx', help='Path to optimized ONNX Re-ID model')
    parser.add_argument('--enroll-dir', type=str, default='data/low_variance_benchmark/gallery', help='Directory containing reference photos of authorized personnel')
    parser.add_argument('--tau', type=float, default=0.7124, help='Score threshold')
    parser.add_argument('--margin', type=float, default=0.05, help='Contrast margin threshold')
    parser.add_argument('--mode', type=str, default='motion', choices=['gate', 'motion'], help="Framing mode: 'gate' for turnstile checkpoint, 'motion' for background subtraction or detection")
    parser.add_argument('--detector', type=str, default='auto', choices=['auto', 'neural', 'motion'], help='Detector architecture')
    parser.add_argument('--max-frames', type=int, default=None, help='Maximum frames to process')
    parser.add_argument('--output-video', type=str, default='data/sample_cctv_annotated.mp4', help='Path to save output video')
    parser.add_argument('--headless', action='store_true', help='Run without GUI display window')
    parser.add_argument('--no-auto-enroll', action='store_true', help='Disable automatic enrollment of reference pedestrian')
    args = parser.parse_args()
    
    pipeline = RealtimeReIDPipeline(onnx_model_path=args.onnx, score_threshold=args.tau, contrast_margin=args.margin, mode=args.mode, detector=args.detector)
    if args.enroll_dir and os.path.exists(args.enroll_dir):
        pipeline.enroll_from_directory(args.enroll_dir)
    pipeline.run_stream(args.source, max_frames=args.max_frames, output_video=args.output_video, headless=args.headless, auto_enroll_lead=not args.no_auto_enroll)
