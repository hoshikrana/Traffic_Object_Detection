# =============================================================================
# TrafficVision — YOLO11 Training & Export Pipeline (Kaggle Notebook)
# =============================================================================
# This script trains a YOLO11-nano model on the VisDrone2019-DET dataset for
# traffic object detection. It handles dataset conversion, training with W&B
# logging, validation, ONNX export, and artifact packaging.
#
# Usage: Paste each "CELL" block into a separate Kaggle notebook cell.
#        Ensure Kaggle secrets contain WANDB_API_KEY.
# =============================================================================


# === CELL 1: SETUP & DEPENDENCIES ============================================
# %% [markdown]
# ## 📦 Cell 1 — Install Dependencies & Authenticate
# Install required packages and configure Weights & Biases for experiment
# tracking. Make sure `WANDB_API_KEY` is set in Kaggle Secrets.

# %%
import subprocess
import sys

# Install required packages
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "ultralytics>=8.3.0",
    "wandb",
    "onnxruntime",
    "rich",
])

import os
import json
import shutil
import random
from pathlib import Path
from collections import defaultdict

import wandb
import ultralytics
import onnxruntime as ort
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from google.colab import userdata  # Kaggle notebooks also expose this

# Authenticate Weights & Biases
os.environ["WANDB_API_KEY"] = userdata.get("WANDB_API_KEY")

console = Console()

# Print library versions
rprint(f"[bold green]✓[/] ultralytics : {ultralytics.__version__}")
rprint(f"[bold green]✓[/] wandb       : {wandb.__version__}")
rprint(f"[bold green]✓[/] onnxruntime : {ort.__version__}")
rprint(f"[bold green]✓[/] Python      : {sys.version.split()[0]}")
print()
rprint("[bold cyan]Setup complete![/]")


# === CELL 2: DOWNLOAD DATASET ================================================
# %% [markdown]
# ## 📥 Cell 2 — Download VisDrone2019-DET Dataset
# Downloads the VisDrone2019-DET dataset from the `ultralytics/visdrone`
# Kaggle dataset. The dataset contains drone-captured images with annotations
# for 10 object categories relevant to traffic analytics.

# %%
from kaggle import api as kaggle_api

DATASET_SLUG = "ultralytics/visdrone"
RAW_DIR = Path("/kaggle/input/visdrone")
WORK_DIR = Path("/kaggle/working")

# Download and extract the dataset
kaggle_api.dataset_download_files(DATASET_SLUG, path=str(RAW_DIR), unzip=True)

# Print directory tree (top 2 levels)
def print_tree(directory: Path, prefix: str = "", max_depth: int = 2, _depth: int = 0):
    """Print a directory tree structure."""
    if _depth >= max_depth:
        return
    entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        if entry.is_dir():
            n_children = sum(1 for _ in entry.rglob("*") if _.is_file())
            rprint(f"{prefix}{connector}[bold blue]{entry.name}/[/] ({n_children} files)")
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(entry, prefix + extension, max_depth, _depth + 1)
        else:
            size_kb = entry.stat().st_size / 1024
            rprint(f"{prefix}{connector}{entry.name} ({size_kb:.1f} KB)")

rprint("\n[bold]📂 Dataset directory structure:[/]")
print_tree(RAW_DIR, max_depth=3)


# === CELL 3: DATASET CONVERSION ==============================================
# %% [markdown]
# ## 🔄 Cell 3 — Convert VisDrone Annotations to YOLO Format
# VisDrone uses `(left, top, width, height)` with space-separated annotation
# files. This cell converts them to YOLO normalized `(cx, cy, w, h)` format,
# creates train/val/test splits, and writes the dataset YAML config.

# %%
# VisDrone category mapping (1-indexed in annotations → 0-indexed for YOLO)
# 0=ignored, 1=pedestrian, 2=people, 3=bicycle, 4=car, 5=van,
# 6=truck, 7=tricycle, 8=awning-tricycle, 9=bus, 10=motor, 11=others
VISDRONE_CLASSES = {
    1: "pedestrian",
    2: "people",
    3: "bicycle",
    4: "car",
    5: "van",
    6: "truck",
    7: "tricycle",
    8: "awning-tricycle",
    9: "bus",
    10: "motor",
}

YOLO_CLASS_NAMES = [VISDRONE_CLASSES[i] for i in sorted(VISDRONE_CLASSES.keys())]
NUM_CLASSES = len(YOLO_CLASS_NAMES)


def convert_visdrone_to_yolo(src_dir: Path, dst_dir: Path) -> dict:
    """
    Convert VisDrone2019-DET annotations to YOLO format.

    VisDrone annotation format (space/comma separated, 12 columns):
        left, top, width, height, score, category, truncation, occlusion, ...

    YOLO format:
        class_id  cx  cy  w  h  (all normalized to [0, 1])

    Args:
        src_dir: Source directory containing 'images/' and 'annotations/' subdirs.
        dst_dir: Destination directory for YOLO-formatted 'images/' and 'labels/'.

    Returns:
        Dictionary with conversion statistics.
    """
    img_src = src_dir / "images"
    ann_src = src_dir / "annotations"

    img_dst = dst_dir / "images"
    lbl_dst = dst_dir / "labels"
    img_dst.mkdir(parents=True, exist_ok=True)
    lbl_dst.mkdir(parents=True, exist_ok=True)

    stats = defaultdict(int)
    stats["total_images"] = 0
    stats["total_boxes"] = 0
    stats["skipped_ignored"] = 0
    stats["skipped_category"] = 0

    # Process each annotation file
    ann_files = sorted(ann_src.glob("*.txt"))
    for ann_file in ann_files:
        stem = ann_file.stem

        # Find matching image (try common extensions)
        img_file = None
        for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            candidate = img_src / (stem + ext)
            if candidate.exists():
                img_file = candidate
                break

        if img_file is None:
            continue

        # Read image dimensions for normalization
        from PIL import Image
        with Image.open(img_file) as img:
            img_w, img_h = img.size

        # Parse annotations
        yolo_lines = []
        with open(ann_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # VisDrone uses comma or space separation
                parts = line.replace(",", " ").split()
                if len(parts) < 8:
                    continue

                left = float(parts[0])
                top = float(parts[1])
                width = float(parts[2])
                height = float(parts[3])
                score = int(parts[4])
                category = int(parts[5])

                # Skip ignored regions (score == 0)
                if score == 0:
                    stats["skipped_ignored"] += 1
                    continue

                # Skip categories not in our mapping (0=ignored, 11=others)
                if category not in VISDRONE_CLASSES:
                    stats["skipped_category"] += 1
                    continue

                # Convert category to 0-indexed YOLO class ID
                class_id = category - 1

                # Convert (left, top, width, height) to YOLO (cx, cy, w, h) normalized
                cx = (left + width / 2.0) / img_w
                cy = (top + height / 2.0) / img_h
                nw = width / img_w
                nh = height / img_h

                # Clamp to [0, 1]
                cx = max(0.0, min(1.0, cx))
                cy = max(0.0, min(1.0, cy))
                nw = max(0.0, min(1.0, nw))
                nh = max(0.0, min(1.0, nh))

                # Skip degenerate boxes
                if nw < 1e-6 or nh < 1e-6:
                    continue

                yolo_lines.append(f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                stats["total_boxes"] += 1
                stats[f"class_{YOLO_CLASS_NAMES[class_id]}"] += 1

        # Copy image and write label file
        shutil.copy2(img_file, img_dst / img_file.name)
        with open(lbl_dst / (stem + ".txt"), "w") as f:
            f.write("\n".join(yolo_lines))
            if yolo_lines:
                f.write("\n")

        stats["total_images"] += 1

    return dict(stats)


# --- Run conversion ---
YOLO_DIR = WORK_DIR / "visdrone_yolo"

# Convert train split
rprint("[bold]Converting train split...[/]")
train_src = None
for candidate in [
    RAW_DIR / "VisDrone2019-DET-train",
    RAW_DIR / "visdrone" / "VisDrone2019-DET-train",
]:
    if candidate.exists():
        train_src = candidate
        break

assert train_src is not None, f"Train split not found under {RAW_DIR}"
train_stats = convert_visdrone_to_yolo(train_src, YOLO_DIR / "train")
rprint(f"  [green]✓[/] Train: {train_stats['total_images']} images, {train_stats['total_boxes']} boxes")

# Convert val split
rprint("[bold]Converting val split...[/]")
val_src = None
for candidate in [
    RAW_DIR / "VisDrone2019-DET-val",
    RAW_DIR / "visdrone" / "VisDrone2019-DET-val",
]:
    if candidate.exists():
        val_src = candidate
        break

assert val_src is not None, f"Val split not found under {RAW_DIR}"
val_stats = convert_visdrone_to_yolo(val_src, YOLO_DIR / "val_full")
rprint(f"  [green]✓[/] Val:   {val_stats['total_images']} images, {val_stats['total_boxes']} boxes")

# --- 90/10 split on val set → val + test ---
rprint("[bold]Splitting val set → 90% val / 10% test...[/]")
val_full_images = sorted((YOLO_DIR / "val_full" / "images").glob("*"))
random.seed(42)
random.shuffle(val_full_images)

split_idx = int(len(val_full_images) * 0.9)
val_images = val_full_images[:split_idx]
test_images = val_full_images[split_idx:]

for split_name, image_list in [("val", val_images), ("test", test_images)]:
    img_dir = YOLO_DIR / split_name / "images"
    lbl_dir = YOLO_DIR / split_name / "labels"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    for img_path in image_list:
        stem = img_path.stem
        shutil.copy2(img_path, img_dir / img_path.name)
        lbl_src = YOLO_DIR / "val_full" / "labels" / (stem + ".txt")
        if lbl_src.exists():
            shutil.copy2(lbl_src, lbl_dir / lbl_src.name)

rprint(f"  [green]✓[/] Val:  {len(val_images)} images")
rprint(f"  [green]✓[/] Test: {len(test_images)} images")

# Clean up val_full
shutil.rmtree(YOLO_DIR / "val_full")

# --- Write dataset YAML ---
YAML_PATH = YOLO_DIR / "visdrone.yaml"
yaml_content = f"""# VisDrone2019-DET Dataset Configuration (YOLO format)
# Auto-generated by TrafficVision training pipeline

path: {YOLO_DIR}
train: train/images
val: val/images
test: test/images

nc: {NUM_CLASSES}
names: {YOLO_CLASS_NAMES}
"""

with open(YAML_PATH, "w") as f:
    f.write(yaml_content)

rprint(f"\n[bold green]✓[/] Dataset YAML written to: {YAML_PATH}")

# Print class distribution table
table = Table(title="Class Distribution (Train)")
table.add_column("Class", style="cyan")
table.add_column("Count", justify="right", style="green")
for cls_name in YOLO_CLASS_NAMES:
    count = train_stats.get(f"class_{cls_name}", 0)
    table.add_row(cls_name, f"{count:,}")
console.print(table)


# === CELL 4: TRAINING =========================================================
# %% [markdown]
# ## 🏋️ Cell 4 — Train YOLO11-nano on VisDrone
# Trains a YOLO11-nano model with aggressive augmentation for drone imagery.
# All metrics, curves, and the best checkpoint are logged to Weights & Biases.

# %%
from ultralytics import YOLO

# Initialize W&B run
run = wandb.init(
    project="traffic-analytics",
    name="yolo11n-visdrone-v1",
    config={
        "model": "yolo11n",
        "dataset": "VisDrone2019-DET",
        "epochs": 80,
        "imgsz": 640,
        "batch": 16,
        "optimizer": "AdamW",
        "lr0": 0.001,
    },
)

# Load pretrained YOLO11-nano
model = YOLO("yolo11n.pt")

# Train
results = model.train(
    data=str(YAML_PATH),
    epochs=80,
    imgsz=640,
    batch=16,
    optimizer="AdamW",
    lr0=0.001,
    warmup_epochs=5,
    mosaic=1.0,
    mixup=0.15,
    copy_paste=0.1,
    degrees=10.0,
    project=str(WORK_DIR / "runs"),
    name="yolo11n-visdrone",
    exist_ok=True,
    verbose=True,
)

# Locate the training run directory
TRAIN_DIR = Path(results.save_dir)
BEST_PT = TRAIN_DIR / "weights" / "best.pt"
assert BEST_PT.exists(), f"best.pt not found at {BEST_PT}"
rprint(f"[bold green]✓[/] Training complete. Best weights: {BEST_PT}")

# Log training artifacts to W&B
artifacts_to_log = {
    "results.csv": TRAIN_DIR / "results.csv",
    "confusion_matrix.png": TRAIN_DIR / "confusion_matrix.png",
    "confusion_matrix_normalized.png": TRAIN_DIR / "confusion_matrix_normalized.png",
    "PR_curve.png": TRAIN_DIR / "PR_curve.png",
    "F1_curve.png": TRAIN_DIR / "F1_curve.png",
    "P_curve.png": TRAIN_DIR / "P_curve.png",
    "R_curve.png": TRAIN_DIR / "R_curve.png",
    "results.png": TRAIN_DIR / "results.png",
}

for name, path in artifacts_to_log.items():
    if path.exists():
        wandb.log({name.replace(".png", "").replace(".csv", ""): wandb.Image(str(path))})
        rprint(f"  [green]✓[/] Logged {name} to W&B")

# Log best.pt as a W&B artifact
model_artifact = wandb.Artifact(
    name="yolo11n-visdrone-best",
    type="model",
    description="YOLO11-nano best checkpoint trained on VisDrone2019-DET",
)
model_artifact.add_file(str(BEST_PT))
run.log_artifact(model_artifact)
rprint("[bold green]✓[/] Logged best.pt as W&B artifact")


# === CELL 5: VALIDATION ======================================================
# %% [markdown]
# ## 📊 Cell 5 — Validate on Test Split
# Runs validation on the held-out test split and prints per-class metrics.
# A soft assertion checks that mAP50 > 0.20 (warning only, does not halt).

# %%
# Load best weights for validation
model = YOLO(str(BEST_PT))

# Run validation on test split
val_results = model.val(
    data=str(YAML_PATH),
    split="test",
    imgsz=640,
    batch=16,
    verbose=True,
)

# Extract metrics
map50 = float(val_results.box.map50)
map50_95 = float(val_results.box.map)
per_class_ap50 = val_results.box.ap50

# Print per-class metrics table
table = Table(title="Per-Class Validation Results (Test Split)")
table.add_column("Class", style="cyan", min_width=18)
table.add_column("AP50", justify="right", style="green")

for i, cls_name in enumerate(YOLO_CLASS_NAMES):
    if i < len(per_class_ap50):
        ap = per_class_ap50[i]
        table.add_row(cls_name, f"{ap:.4f}")

table.add_section()
table.add_row("[bold]mAP50[/]", f"[bold]{map50:.4f}[/]")
table.add_row("[bold]mAP50-95[/]", f"[bold]{map50_95:.4f}[/]")
console.print(table)

# Soft assertion on mAP50
MAP50_THRESHOLD = 0.20
if map50 > MAP50_THRESHOLD:
    rprint(f"[bold green]✓[/] mAP50 = {map50:.4f} > {MAP50_THRESHOLD} — PASS")
else:
    rprint(f"[bold yellow]⚠[/] mAP50 = {map50:.4f} <= {MAP50_THRESHOLD} — "
           f"Below threshold! Continuing with warning...")

# Log validation metrics to W&B
wandb.log({
    "test/mAP50": map50,
    "test/mAP50-95": map50_95,
    **{f"test/AP50/{YOLO_CLASS_NAMES[i]}": float(per_class_ap50[i])
       for i in range(min(len(per_class_ap50), NUM_CLASSES))},
})
rprint("[bold green]✓[/] Validation metrics logged to W&B")


# === CELL 6: EXPORT ONNX =====================================================
# %% [markdown]
# ## 📦 Cell 6 — Export to ONNX
# Exports the trained model to ONNX format for CPU inference. The exported
# model is verified with ONNX Runtime to confirm correct output shapes.

# %%
import numpy as np

# Export to ONNX
model = YOLO(str(BEST_PT))
onnx_path = model.export(
    format="onnx",
    simplify=True,
    opset=17,
    imgsz=640,
)
onnx_path = Path(onnx_path)
rprint(f"[bold green]✓[/] ONNX exported to: {onnx_path}")
rprint(f"  File size: {onnx_path.stat().st_size / (1024 * 1024):.2f} MB")

# Verify with ONNX Runtime
session = ort.InferenceSession(str(onnx_path))

rprint("\n[bold]Input tensors:[/]")
for inp in session.get_inputs():
    rprint(f"  {inp.name}: shape={inp.shape}, dtype={inp.type}")

rprint("\n[bold]Output tensors:[/]")
for out in session.get_outputs():
    rprint(f"  {out.name}: shape={out.shape}, dtype={out.type}")

# Run a dummy inference to verify
dummy_input = np.random.randn(1, 3, 640, 640).astype(np.float32)
input_name = session.get_inputs()[0].name
outputs = session.run(None, {input_name: dummy_input})

rprint("\n[bold]Inference verification:[/]")
for i, out in enumerate(outputs):
    rprint(f"  Output[{i}]: shape={out.shape}, dtype={out.dtype}")

rprint("[bold green]✓[/] ONNX model verified successfully!")


# === CELL 7: SAVE ARTIFACTS ==================================================
# %% [markdown]
# ## 💾 Cell 7 — Package Artifacts for Download
# Packages the best ONNX model, dataset config, class map, and model metadata
# into a single artifacts directory. Everything is logged to W&B for easy
# retrieval.

# %%
ARTIFACTS_DIR = WORK_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Copy best ONNX model
shutil.copy2(onnx_path, ARTIFACTS_DIR / "best.onnx")
rprint("[green]✓[/] Copied best.onnx")

# 2. Copy dataset YAML
shutil.copy2(YAML_PATH, ARTIFACTS_DIR / "visdrone.yaml")
rprint("[green]✓[/] Copied visdrone.yaml")

# 3. Create class_map.json
class_map = {str(i): name for i, name in enumerate(YOLO_CLASS_NAMES)}
class_map_path = ARTIFACTS_DIR / "class_map.json"
with open(class_map_path, "w") as f:
    json.dump(class_map, f, indent=2)
rprint("[green]✓[/] Created class_map.json")

# 4. Create model_info.json
model_info = {
    "model_name": "yolo11n-visdrone",
    "architecture": "YOLO11-nano",
    "dataset": "VisDrone2019-DET",
    "num_classes": NUM_CLASSES,
    "class_names": YOLO_CLASS_NAMES,
    "input_size": [1, 3, 640, 640],
    "format": "ONNX",
    "opset": 17,
    "training": {
        "epochs": 80,
        "imgsz": 640,
        "batch_size": 16,
        "optimizer": "AdamW",
        "lr0": 0.001,
        "augmentation": {
            "mosaic": 1.0,
            "mixup": 0.15,
            "copy_paste": 0.1,
            "degrees": 10.0,
        },
    },
    "metrics": {
        "mAP50": round(map50, 4),
        "mAP50-95": round(map50_95, 4),
    },
    "onnx_file_size_mb": round(onnx_path.stat().st_size / (1024 * 1024), 2),
}

model_info_path = ARTIFACTS_DIR / "model_info.json"
with open(model_info_path, "w") as f:
    json.dump(model_info, f, indent=2)
rprint("[green]✓[/] Created model_info.json")

# Print artifacts directory tree
rprint("\n[bold]📂 Artifacts directory:[/]")
for f in sorted(ARTIFACTS_DIR.iterdir()):
    size = f.stat().st_size
    if size > 1024 * 1024:
        size_str = f"{size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{size / 1024:.1f} KB"
    rprint(f"  └── {f.name} ({size_str})")

# Log artifacts to W&B
export_artifact = wandb.Artifact(
    name="yolo11n-visdrone-export",
    type="deployment",
    description="YOLO11-nano ONNX model + metadata for TrafficVision deployment",
)
export_artifact.add_dir(str(ARTIFACTS_DIR))
run.log_artifact(export_artifact)
rprint("\n[bold green]✓[/] Artifacts logged to W&B")

# Finish W&B run
wandb.finish()

rprint("\n" + "=" * 60)
rprint("[bold green]🎉 Training pipeline complete![/]")
rprint("=" * 60)
rprint(f"\n[bold]Next steps:[/]")
rprint("  1. Download artifacts from /kaggle/working/artifacts/")
rprint("  2. Place best.onnx in your project's models/ directory")
rprint("  3. Copy class_map.json to your backend config")
rprint("  4. Run the inference pipeline locally")
rprint(f"\n  mAP50    = {map50:.4f}")
rprint(f"  mAP50-95 = {map50_95:.4f}")
