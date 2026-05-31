"""Main inference engine — processes video, runs YOLO + ByteTrack, writes annotated output."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import cv2
import numpy as np
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from ultralytics import YOLO

from .analytics import TrafficAnalytics
from .annotator import FrameAnnotator
from .config import (
    ANALYTICS_SEND_EVERY_N_FRAMES,
    CONF_THRESHOLD,
    IOU_THRESHOLD,
    PIXELS_PER_METER,
    VISDRONE_CLASSES,
    CLASS_CONF_THRESHOLDS,
)
from .sender import AnalyticsSender

logger = logging.getLogger(__name__)
console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Traffic Analytics Inference Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model", type=str, required=True, help="Path to YOLO model (OpenVINO dir or .pt file)"
    )
    parser.add_argument(
        "--video", type=str, required=True, help="Path to input .mp4 video file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_annotated.mp4",
        help="Path to save annotated output .mp4",
    )
    parser.add_argument(
        "--job-id", type=str, required=True, help="Job ID from FastAPI backend"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of FastAPI backend",
    )
    parser.add_argument(
        "--skip", type=int, default=2, help="Process every Nth frame"
    )
    return parser.parse_args()


async def main() -> None:
    """Main async entry point."""
    args = parse_args()

    console.print("[bold cyan]Traffic Analytics Inference Engine[/bold cyan]")
    console.print(f"  Model:  {args.model}")
    console.print(f"  Video:  {args.video}")
    console.print(f"  Output: {args.output}")
    console.print(f"  Job ID: {args.job_id}")
    console.print(f"  API:    {args.api_url}")
    console.print(f"  Skip:   every {args.skip} frames")
    console.print()

    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # 1. Load model
    console.print("[yellow]Loading model...[/yellow]")
    model_path = args.model
    if not Path(model_path).exists():
        console.print(f"[orange3]WARNING: Model path '{model_path}' not found.[/orange3]")
        console.print("[yellow]Falling back to default 'yolo11n.pt' for processing...[/yellow]")
        model_path = "yolo11n.pt"

    model = YOLO(model_path)
    console.print(f"[green]Model loaded:[/green] {model.model_name if hasattr(model, 'model_name') else model_path}")

    # Warm up with a dummy inference
    dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
    model(dummy_frame, verbose=False)
    console.print("[green]Model warm-up complete[/green]")

    # Extract dynamic class mapping from the model
    model_names = model.names if hasattr(model, "names") and model.names else VISDRONE_CLASSES
    vehicle_keywords = {"car", "van", "truck", "bus", "motorcycle", "bicycle", "tricycle", "motor", "vehicle"}
    vehicle_class_ids = {
        cid for cid, name in model_names.items()
        if any(kw in name.lower() for kw in vehicle_keywords)
    }
    console.print(f"[green]Dynamic vehicle class IDs detected from model names:[/green] {list(vehicle_class_ids)}")

    # 2. Open video
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        console.print(f"[red]ERROR: Cannot open video: {args.video}[/red]")
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    console.print(f"  Video: {width}x{height} @ {fps:.1f} FPS, {total_frames} frames")

    # Create output writer with native web browser H.264 (avc1/X264/H264) codec support, fallback if needed
    writer = None
    attempted_codecs = ["avc1", "X264", "H264", "mp4v"]
    for codec in attempted_codecs:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(args.output, fourcc, fps, (width, height))
            if writer.isOpened():
                console.print(f"[green]Successfully initialized VideoWriter with codec '{codec}' for web compatibility.[/green]")
                break
            else:
                writer.release()
                writer = None
        except Exception as exc:
            console.print(f"[yellow]Codec '{codec}' failed: {exc}[/yellow]")
            if writer:
                writer.release()
                writer = None

    if writer is None or not writer.isOpened():
        console.print(f"[red]ERROR: Cannot create output video with any of the attempted codecs: {args.output}[/red]")
        sys.exit(1)

    # 3. Initialize components
    analytics_engine = TrafficAnalytics(fps, PIXELS_PER_METER, vehicle_class_ids=vehicle_class_ids, class_names=model_names)
    annotator = FrameAnnotator()
    sender = AnalyticsSender(args.job_id, args.api_url)

    # 4. Frame processing loop
    frame_idx = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing frames", total=total_frames)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            progress.update(task, completed=frame_idx)

            # Skip frames to maintain processing speed
            if frame_idx % args.skip != 0:
                writer.write(frame)  # write unannotated to keep video length
                continue

            # Run YOLO inference with ByteTrack tracking
            results = model.track(
                frame,
                persist=True,
                conf=CONF_THRESHOLD,
                iou=IOU_THRESHOLD,
                tracker="bytetrack.yaml",
                verbose=False,
            )

            # Parse detections
            detections = []
            if (
                results
                and results[0].boxes is not None
                and results[0].boxes.id is not None
            ):
                boxes = results[0].boxes
                for i in range(len(boxes)):
                    x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    class_id = int(boxes.cls[i])
                    conf = float(boxes.conf[i])

                    # Apply class-specific confidence threshold filtering to eliminate landscape false positives
                    class_name = model_names.get(class_id, "unknown").lower()
                    target_threshold = CONF_THRESHOLD
                    for kw, th in CLASS_CONF_THRESHOLDS.items():
                        if kw in class_name:
                            target_threshold = th
                            break

                    if conf < target_threshold:
                        continue # Filter out false positive background detections!

                    detections.append(
                        {
                            "track_id": int(boxes.id[i]),
                            "class_id": class_id,
                            "conf": conf,
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "cx": cx,
                            "cy": cy,
                        }
                    )

            # Update analytics
            analytics = analytics_engine.update(detections, height, width)

            # Annotate frame
            annotated = annotator.draw(
                frame.copy(),
                detections,
                analytics_engine.track_positions,
                analytics_engine.track_speeds,
                analytics_engine.track_classes,
                analytics,
                class_names=model_names,
            )

            # Write annotated frame
            writer.write(annotated)

            # Send analytics periodically
            if frame_idx % ANALYTICS_SEND_EVERY_N_FRAMES == 0:
                progress_pct = (frame_idx / total_frames) * 100
                await sender.send_analytics(analytics, progress_pct)

    # Cleanup
    cap.release()
    writer.release()

    # Send completion with summary
    summary = analytics_engine.get_summary()
    summary["output_video_path"] = str(Path(args.output).resolve())
    await sender.send_complete(summary)
    await sender.close()

    # Print final summary table
    console.print()
    table = Table(title="Inference Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Total Frames", str(summary["total_frames_processed"]))
    table.add_row("Unique Vehicles", str(summary["total_unique_vehicles"]))
    table.add_row("Peak Count", str(summary["peak_vehicle_count"]))
    table.add_row("Total Incidents", str(summary["total_incidents"]))
    table.add_row("Total Crossings", str(summary["total_crossings"]))
    table.add_row("Avg Speed", f"{summary['avg_speed_overall']} km/h")
    table.add_row("API Sends (OK/Fail)", f"{sender.success_count}/{sender.failed_count}")
    console.print(table)
    console.print(f"\n[bold green]Annotated video saved to:[/bold green] {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
