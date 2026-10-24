import os
import sys
import unittest
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openset_reid.pipeline.video_analyzer import (
    IdentityStatus,
    PassageStatus,
    PersonCategory,
    resolve_display_category,
    OfflineVideoAnalyzer
)

class TestOfflineReIDPipeline(unittest.TestCase):

    def test_status_decoupling_and_precedence(self):
        cat1 = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.FIRST_ENTRY)
        self.assertEqual(cat1, PersonCategory.OFFICIAL_WORKER)

        cat2 = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.PASSAGE_IN_PROGRESS)
        self.assertEqual(cat2, PersonCategory.OFFICIAL_WORKER)

        cat3 = resolve_display_category(IdentityStatus.OFFICIAL_WORKER, PassageStatus.REPEAT_PASSAGE)
        self.assertEqual(cat3, PersonCategory.PREVIOUSLY_ENROLLED)

        cat4 = resolve_display_category(IdentityStatus.NEW_CANDIDATE, PassageStatus.FIRST_ENTRY)
        self.assertEqual(cat4, PersonCategory.NEW_PERSON)

        cat5 = resolve_display_category(IdentityStatus.UNKNOWN, PassageStatus.PASSAGE_IN_PROGRESS)
        self.assertEqual(cat5, PersonCategory.UNKNOWN)

    def test_crop_quality_assessment(self):
        analyzer = OfflineVideoAnalyzer(
            score_threshold=0.7124,
            contrast_margin=0.05,
            quality_min_h=30,
            quality_min_w=15,
            quality_min_blur=25.0
        )
        
        sharp_crop = np.random.randint(0, 255, (64, 32, 3), dtype=np.uint8)
        is_ok, blur_v, q_score = analyzer.assess_crop_quality(sharp_crop)
        self.assertTrue(is_ok)
        self.assertGreater(blur_v, 0.0)
        self.assertGreater(q_score, 0.0)

        tiny_crop = np.random.randint(0, 255, (20, 10, 3), dtype=np.uint8)
        is_ok_tiny, _, _ = analyzer.assess_crop_quality(tiny_crop)
        self.assertFalse(is_ok_tiny)

        flat_crop = np.full((64, 32, 3), 128, dtype=np.uint8)
        is_ok_flat, blur_v_flat, _ = analyzer.assess_crop_quality(flat_crop)
        self.assertFalse(is_ok_flat)
        self.assertLess(blur_v_flat, 25.0)

    def test_end_to_end_synthetic_video_analysis(self):
        analyzer = OfflineVideoAnalyzer(
            score_threshold=0.7124,
            contrast_margin=0.05
        )
        
        test_video_path = 'data/test_synthetic.mp4'
        os.makedirs('data', exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        vw = cv2.VideoWriter(test_video_path, fourcc, 25.0, (640, 360))
        
        for f in range(30):
            frame = np.full((360, 640, 3), 200, dtype=np.uint8)
            cv2.rectangle(frame, (100 + f * 2, 100), (140 + f * 2, 220), (50, 50, 150), -1)
            vw.write(frame)
        vw.release()

        crops_dir = 'experiments/crops/test_synthetic'
        json_report = 'experiments/reports/test_synthetic_report.json'
        output_vid = 'data/test_synthetic_annotated.mp4'

        summary = analyzer.analyze_video(
            video_path=test_video_path,
            output_video_path=output_vid,
            output_crops_dir=crops_dir,
            output_json_path=json_report,
            max_frames=30,
            auto_enroll_lead_worker=False
        )

        self.assertIn('total_frames_processed', summary)
        self.assertEqual(summary['total_frames_processed'], 30)
        self.assertIn('categories', summary)
        self.assertIn('tracks', summary)
        self.assertTrue(os.path.exists(json_report))
        self.assertTrue(os.path.exists(output_vid))

        if os.path.exists(test_video_path):
            os.remove(test_video_path)
        if os.path.exists(output_vid):
            os.remove(output_vid)

if __name__ == '__main__':
    unittest.main()
