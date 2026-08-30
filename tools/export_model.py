"""Export YOLO model to mobile-accelerated formats (NCNN / ONNX)."""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path and load Android patch
sys.path.insert(0, str(Path(__file__).parent.parent))
import utils.android_patch  # noqa: F401

from ultralytics import YOLO


def export_model(model_path: str, export_format: str = "ncnn", imgsz: int = 416):
    print(f"Loading '{model_path}' and exporting to format '{export_format}' with imgsz={imgsz}...")
    model = YOLO(model_path)
    output_path = model.export(format=export_format, imgsz=imgsz)
    print(f"\n🎉 SUCCESS: Model exported to: {output_path}")
    print(f"👉 To use this on Android, set MODEL_NAME={output_path} in your .env file!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export YOLO model for mobile acceleration")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Path to .pt model")
    parser.add_argument("--format", type=str, default="ncnn", choices=["ncnn", "onnx", "tflite", "torchscript"], help="Export format")
    parser.add_argument("--imgsz", type=int, default=416, help="Inference image size (e.g. 416 or 320)")
    args = parser.parse_args()

    export_model(args.model, args.format, args.imgsz)
