"""
Media Evaluation Tool for Testing Historical Images & Videos.

Allows offline verification of recorded camera frames, snapshots, and video clips
to evaluate model detection performance, bounding boxes, and confidence thresholds.
"""

import sys
import argparse
import time
from pathlib import Path
import cv2
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import utils.android_patch  # noqa: F401
from config import config
from detection.yolo_detector import YOLODetector
from evidence.storage import EvidenceStorage
from events.models import ConfirmedAlertEvent, FrameDetectionResult, Detection, BoundingBox
from datetime import datetime


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".ts"}


def evaluate_image_file(detector: YOLODetector, storage: EvidenceStorage, file_path: Path, output_dir: Path):
    """Evaluates a single image file."""
    frame = cv2.imread(str(file_path))
    if frame is None:
        print(f"❌ Could not read image: {file_path}")
        return False, []

    res = detector.detect(frame)
    h, w = frame.shape[:2]
    
    print(f"\n📄 Image: {file_path.name} ({w}x{h})")
    print(f"   Inference Latency: {res.inference_time_ms:.1f} ms")

    if res.has_targets:
        print(f"   🎯 Detected {len(res.detections)} target(s):")
        for i, det in enumerate(res.detections, 1):
            x1, y1, x2, y2 = det.bbox.to_int_tuple()
            print(f"      #{i}: {det.class_name.upper()} | Confidence: {det.confidence:.1%} | Box: [{x1}, {y1}, {x2}, {y2}]")
        
        # Save annotated image
        event = ConfirmedAlertEvent(
            event_id=file_path.stem[:8],
            triggered_at=datetime.now(),
            confirmed_detections=[res],
            best_result=res
        )
        saved_path = storage.save_event_evidence(event)
        print(f"   💾 Saved annotated output: {saved_path}")
        return True, res.detections
    else:
        print("   ⚪ No targets detected above confidence threshold.")
        return False, []


def evaluate_video_file(detector: YOLODetector, storage: EvidenceStorage, video_path: Path, output_dir: Path, sample_fps: float = 1.0):
    """Evaluates a recorded video clip frame by frame at specified sample FPS."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / video_fps if video_fps > 0 else 0
    frame_interval = max(1, int(round(video_fps / sample_fps)))

    print(f"\n🎬 Processing Video: {video_path.name}")
    print(f"   Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"   Native FPS: {video_fps:.1f} | Duration: {duration_sec:.1f}s | Sample Interval: every {frame_interval} frames (~{sample_fps} FPS)")

    frame_idx = 0
    samples_checked = 0
    detections_found = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if frame_idx % frame_interval == 0:
            samples_checked += 1
            timestamp_sec = frame_idx / video_fps
            res = detector.detect(frame)

            if res.has_targets:
                detections_found += 1
                best_det = res.best_detection
                print(f"   ⏱️  [{timestamp_sec:.1f}s] Frame #{frame_idx}: 🎯 {best_det.class_name.upper()} ({best_det.confidence:.1%})")
                
                event = ConfirmedAlertEvent(
                    event_id=f"{video_path.stem}_f{frame_idx}",
                    triggered_at=datetime.now(),
                    confirmed_detections=[res],
                    best_result=res
                )
                storage.save_event_evidence(event)

        frame_idx += 1

    cap.release()
    print(f"\n🏁 Video Evaluation Completed:")
    print(f"   Total Samples Tested: {samples_checked}")
    print(f"   Detections Found:     {detections_found}")


def main():
    parser = argparse.ArgumentParser(description="Offline Media Evaluator for Predator / Cat Detection")
    parser.add_argument(
        "--source",
        type=str,
        default="./test_inputs",
        help="Path to an image file, video file, or a directory containing media files."
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=config.CONFIDENCE_THRESHOLD,
        help=f"Confidence threshold (0.0 to 1.0, default: {config.CONFIDENCE_THRESHOLD})"
    )
    parser.add_argument(
        "--classes",
        type=str,
        default=",".join(config.TARGET_CLASSES),
        help=f"Comma-separated target classes to detect (default: {','.join(config.TARGET_CLASSES)})"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./test_outputs",
        help="Directory to store annotated results."
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=config.DETECTION_FPS,
        help=f"Sampling FPS when processing video files (default: {config.DETECTION_FPS})"
    )

    args = parser.parse_args()

    target_classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" 🧪 Predator Camera Media Evaluator")
    print(f" Source:               {args.source}")
    print(f" Model:                {config.MODEL_NAME}")
    print(f" Target Classes:       {target_classes}")
    print(f" Confidence Threshold: {args.conf:.2f}")
    print(f" Output Directory:     {output_path.resolve()}")
    print("=" * 60)

    detector = YOLODetector(
        model_name=config.MODEL_NAME,
        target_classes=target_classes,
        confidence_threshold=args.conf,
        imgsz=config.INFERENCE_IMAGE_SIZE
    )

    storage = EvidenceStorage(
        base_dir=output_path,
        save_annotated=True,
        save_raw=False
    )

    source_path = Path(args.source)

    if not source_path.exists():
        print(f"\n⚠️ Source path does not exist: {source_path.resolve()}")
        print(f"   Please place your historical photos/videos into {source_path.resolve()} and re-run.")
        return

    if source_path.is_file():
        ext = source_path.suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            evaluate_image_file(detector, storage, source_path, output_path)
        elif ext in VIDEO_EXTENSIONS:
            evaluate_video_file(detector, storage, source_path, output_path, sample_fps=args.fps)
        else:
            print(f"❌ Unsupported file format: {ext}")
    elif source_path.is_dir():
        media_files = [
            f for f in sorted(source_path.iterdir())
            if f.suffix.lower() in (IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
        ]

        if not media_files:
            print(f"\n⚠️ No supported image or video files found in: {source_path.resolve()}")
            print(f"   Supported formats: {', '.join(sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS))}")
            return

        print(f"\nFound {len(media_files)} media file(s) to evaluate...")
        total_detections = 0
        for f in media_files:
            ext = f.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                has_det, _ = evaluate_image_file(detector, storage, f, output_path)
                if has_det:
                    total_detections += 1
            elif ext in VIDEO_EXTENSIONS:
                evaluate_video_file(detector, storage, f, output_path, sample_fps=args.fps)

        print("\n" + "=" * 60)
        print(f"📊 SUMMARY: {total_detections}/{len(media_files)} image(s) had positive predator detections.")
        print(f"📁 Annotated evidence saved to: {output_path.resolve()}")
        print("=" * 60)


if __name__ == "__main__":
    main()
