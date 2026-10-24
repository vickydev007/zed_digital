import os
import sys
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openset_reid.pipeline.video_analyzer import OfflineVideoAnalyzer

def main():
    parser = argparse.ArgumentParser(description='Offline Person Re-ID Video Analysis Pipeline')
    parser.add_argument('--video', type=str, default='data/sample_cctv.mp4', help='Path to uploaded input video file')
    parser.add_argument('--output-video', type=str, default='data/sample_cctv_offline_annotated.mp4', help='Path to save annotated MP4 video')
    parser.add_argument('--crops-dir', type=str, default='experiments/crops/sample_cctv', help='Directory to store representative person crops')
    parser.add_argument('--output-json', type=str, default='experiments/reports/sample_cctv_offline_report.json', help='Path to save structured JSON analysis report')
    parser.add_argument('--gallery-dir', type=str, default='data/low_variance_benchmark/gallery', help='Directory containing reference images of authorized workers')
    parser.add_argument('--tau', type=float, default=0.7124, help='Calibrated acceptance score threshold')
    parser.add_argument('--margin', type=float, default=0.05, help='Ambiguity contrast margin threshold')
    parser.add_argument('--max-frames', type=int, default=200, help='Maximum frames to process')
    parser.add_argument('--no-auto-enroll', action='store_true', help='Disable automatic enrollment of reference lead worker')
    args = parser.parse_args()

    analyzer = OfflineVideoAnalyzer(
        score_threshold=args.tau,
        contrast_margin=args.margin
    )

    if args.gallery_dir and os.path.exists(args.gallery_dir):
        enrolled_count = analyzer.enroll_from_directory(args.gallery_dir)
        print(f'Enrolled {enrolled_count} worker references from {args.gallery_dir}')

    print(f'Starting offline video analysis on: {args.video}...')
    summary = analyzer.analyze_video(
        video_path=args.video,
        output_video_path=args.output_video,
        output_crops_dir=args.crops_dir,
        output_json_path=args.output_json,
        max_frames=args.max_frames,
        auto_enroll_lead_worker=not args.no_auto_enroll
    )

    print('\n' + '=' * 65)
    print('  OFFLINE VIDEO ANALYSIS COMPLETED SUCCESSFULLY')
    print('=' * 65)
    print(f"  Frames Processed:   {summary['total_frames_processed']}")
    print(f"  Average FPS:        {summary['average_fps']:.1f}")
    print(f"  Total Tracks:       {summary['total_tracks']}")
    print(f"  Official Workers:   {summary['categories']['OFFICIAL_WORKER']}")
    print(f"  Repeat Passages:    {summary['categories']['PREVIOUSLY_ENROLLED']}")
    print(f"  New Persons:        {summary['categories']['NEW_PERSON']}")
    print(f"  Unknown / Low Qual: {summary['categories']['UNKNOWN']}")
    print(f"  Output Video:       {summary['output_video']}")
    print(f"  JSON Report:        {args.output_json}")
    print('=' * 65 + '\n')

if __name__ == '__main__':
    main()
