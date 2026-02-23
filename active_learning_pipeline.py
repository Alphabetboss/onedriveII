#!/usr/bin/env python3
r"""
active_learning_pipeline.py
Ingenious Irrigation â€” bulk ingest + active learning + (optional) train.

What it does:
1) INGEST:
   - Pulls new images from .\incoming\images and frames from videos in .\incoming\videos
   - De-duplicates by SHA1
   - Drops everything into .\dataset\unlabeled

2) SELECT (Active Learning):
   - Runs YOLO on unlabeled images with your model
   - If no detections OR low/ambiguous confidence -> moves to .\dataset\to_label
   - If confident -> auto-writes YOLO labels and moves to .\dataset\autolabeled

3) PREP DATA:
   - Merges .\dataset\labeled and .\dataset\autolabeled
   - Splits into train/val under .\dataset\yolo\{images,labels}\{train,val}
   - Writes a run log CSV to .\pipeline_runs\log.csv

4) (Optional) TRAIN:
   - If --train is passed, launches ultralytics training using your data.yaml

You can run stages separately: --ingest, --select, --prep, --train, or --all
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import List, Tuple, Dict

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

# ---- Ultralytics (YOLOv8) ----
try:
    from ultralytics import YOLO
except Exception as e:
    print("[ERR] ultralytics not installed. Run: pip install ultralytics")
    raise

# ---------------- CONFIG / DEFAULTS ----------------
ROOT = Path(".").resolve()
INCOMING_IMG = ROOT / "incoming" / "images"
INCOMING_VID = ROOT / "incoming" / "videos"
DATASET = ROOT / "dataset"
UNLABELED_DIR = DATASET / "unlabeled"
TO_LABEL_DIR = DATASET / "to_label"
AUTOLABELED_DIR = DATASET / "autolabeled"
# human-labeled YOLO files live here (images+txt)
LABELED_DIR = DATASET / "labeled"

YOLO_OUT = DATASET / "yolo"
YOLO_IMGS = YOLO_OUT / "images"
YOLO_LABS = YOLO_OUT / "labels"

RUNS_DIR = ROOT / "pipeline_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
LOG_CSV = RUNS_DIR / "log.csv"

# Your classes (index order matters)
CLASSES = [
    "healthy_grass",
    "dry_grass",
    "water",
    "standing_water",
    "mud",
    "mushy_grass",
    "leak",
    "sprinkler"
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

# ---------------- UTILS ----------------


def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dirs():
    for d in [INCOMING_IMG, INCOMING_VID, UNLABELED_DIR, TO_LABEL_DIR, AUTOLABELED_DIR, LABELED_DIR,
              YOLO_IMGS/"train", YOLO_IMGS/"val", YOLO_LABS/"train", YOLO_LABS/"val"]:
        d.mkdir(parents=True, exist_ok=True)


def safe_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_yolo_labels(label_path: Path, boxes_xywhn: np.ndarray, cls_ids: np.ndarray):
    """boxes_xywhn: normalized [x,y,w,h], cls_ids: int"""
    lines = []
    for (x, y, w, h), c in zip(boxes_xywhn, cls_ids):
        lines.append(f"{int(c)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
    label_path.write_text("\n".join(lines))


def save_log(rows: List[Dict]):
    df = pd.DataFrame(rows)
    if LOG_CSV.exists():
        old = pd.read_csv(LOG_CSV)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(LOG_CSV, index=False)


def to_numpy(x):
    """
    Robustly convert a value to a numpy array:
    - If it's already a numpy.ndarray, return as-is.
    - If it's a torch tensor (has .cpu()), move to CPU and call .numpy().
    - If it has a .numpy() method, call that.
    - Otherwise, wrap with np.array().
    """
    if isinstance(x, np.ndarray):
        return x
    if hasattr(x, "cpu"):
        return x.cpu().numpy()
    if hasattr(x, "numpy"):
        return x.numpy()
    return np.array(x)


def video_to_frames(video_path: Path, out_dir: Path, every_n_sec: float = 1.0):
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[WARN] Could not open video: {video_path}")
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = int(max(1, round(fps * every_n_sec)))
    count, saved = 0, 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if count % step == 0:
            name = f"{video_path.stem}_f{count:06d}.jpg"
            out = out_dir / name
            cv2.imwrite(str(out), frame)
            saved += 1
        count += 1
    cap.release()
    return saved

# ---------------- 1) INGEST ----------------


def stage_ingest() -> List[Path]:
    ensure_dirs()
    print("[INGEST] Scanning incoming images and videos...")
    new_paths: List[Path] = []

    # Extract frames from videos
    for vp in sorted(INCOMING_VID.glob("*")):
        if vp.suffix.lower() not in VIDEO_EXTS:
            continue
        frames_saved = video_to_frames(vp, INCOMING_IMG, every_n_sec=1.0)
        print(f"[INGEST] Extracted {frames_saved} frames from {vp.name}")

    # Copy images into unlabeled, skipping dupes by hash
    seen_hashes = {}
    hash_index_path = RUNS_DIR / "hash_index.json"
    if hash_index_path.exists():
        seen_hashes = json.loads(hash_index_path.read_text())

    for ip in sorted(INCOMING_IMG.glob("*")):
        if ip.suffix.lower() not in IMAGE_EXTS:
            continue
        h = sha1_of_file(ip)
        if h in seen_hashes:
            continue
        dest = UNLABELED_DIR / ip.name
        safe_copy(ip, dest)
        seen_hashes[h] = dest.name
        new_paths.append(dest)

    hash_index_path.write_text(json.dumps(seen_hashes, indent=2))
    print(f"[INGEST] New images moved to unlabeled: {len(new_paths)}")
    return new_paths

# ---------------- 2) SELECT (Active Learning) ----------------


def load_model(weights: Path | None):
    if weights and Path(weights).exists():
        print(f"[MODEL] Loading {weights}")
        return YOLO(str(weights))
    else:
        print("[MODEL] Custom weights not found. Falling back to yolov8n.pt")
        return YOLO("yolov8n.pt")


def stage_select(model_path: Path | None, imgsz: int, conf_low: float, conf_high: float) -> Dict[str, int]:
    ensure_dirs()
    model = load_model(model_path)
    unlabeled = sorted([p for p in UNLABELED_DIR.glob("*")
                       if p.suffix.lower() in IMAGE_EXTS])
    stats = {"scanned": 0, "to_label": 0, "autolabeled": 0, "errors": 0}
    rows = []

    for img in tqdm(unlabeled, desc="[SELECT] scoring"):
        stats["scanned"] += 1
        try:
            # Run prediction
            res = model.predict(source=str(img), imgsz=imgsz,
                                conf=0.001, verbose=False)[0]
            det_count = 0 if res.boxes is None else res.boxes.shape[0]

            # If no detections -> needs human label
            if det_count == 0:
                dest = TO_LABEL_DIR / img.name
                safe_copy(img, dest)
                stats["to_label"] += 1
                rows.append({"file": img.name, "route": "to_label",
                             "reason": "no_detections"})
                img.unlink(missing_ok=True)
                continue

            # Compute heuristics
            boxes = res.boxes
            if boxes is None:
                # Defensive fallback: if boxes unexpectedly None, treat as no detections
                dest = TO_LABEL_DIR / img.name
                safe_copy(img, dest)
                stats["to_label"] += 1
                rows.append({"file": img.name, "route": "to_label",
                             "reason": "no_detections"})
                img.unlink(missing_ok=True)
                continue

            # Use to_numpy helper to support both torch tensors and numpy arrays
            confs = to_numpy(boxes.conf)
            cls = to_numpy(boxes.cls).astype(int)
            xywhn = to_numpy(boxes.xywhn)

            max_conf = float(confs.max()) if len(confs) else 0.0
            mean_conf = float(confs.mean()) if len(confs) else 0.0

            # Ambiguity heuristic: small margin between top two confidences
            sorted_confs = sorted(confs, reverse=True)
            margin = sorted_confs[0] - \
                (sorted_confs[1] if len(sorted_confs) > 1 else 0.0)

            uncertain = (max_conf <= conf_low) or (
                conf_low < max_conf <= conf_high) or (margin < 0.10)

            if uncertain:
                dest = TO_LABEL_DIR / img.name
                safe_copy(img, dest)
                stats["to_label"] += 1
                rows.append({"file": img.name, "route": "to_label",
                             "reason": f"uncertain(max={max_conf:.2f},mean={mean_conf:.2f},margin={margin:.2f})"})
                img.unlink(missing_ok=True)
            else:
                # Confident -> auto-label
                dest_img = AUTOLABELED_DIR / img.name
                dest_lab = AUTOLABELED_DIR / (img.stem + ".txt")
                safe_copy(img, dest_img)
                write_yolo_labels(dest_lab, xywhn, cls)
                stats["autolabeled"] += 1
                rows.append({"file": img.name, "route": "autolabeled",
                             "reason": f"confident(max={max_conf:.2f})"})
                img.unlink(missing_ok=True)

        except Exception as e:
            stats["errors"] += 1
            rows.append(
                {"file": img.name, "route": "error", "reason": repr(e)})

    save_log(rows)
    print(
        f"[SELECT] -> to_label: {stats['to_label']}, autolabeled: {stats['autolabeled']}, errors: {stats['errors']}")
    return stats

# ---------------- 3) PREP YOLO DATASET ----------------


def stage_prep(val_split: float = 0.15) -> Tuple[int, int]:
    ensure_dirs()

    # gather all labeled (human) + autolabeled
    sources = []
    for d in [LABELED_DIR, AUTOLABELED_DIR]:
        for img in d.glob("*"):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            txt = img.with_suffix(".txt")
            if not txt.exists():
                continue
            sources.append((img, txt))

    random.shuffle(sources)
    n_total = len(sources)
    n_val = max(1, int(n_total * val_split)) if n_total else 0

    # clear current train/val
    for p in [YOLO_IMGS/"train", YOLO_IMGS/"val", YOLO_LABS/"train", YOLO_LABS/"val"]:
        for f in p.glob("*"):
            f.unlink()

    # split+copy
    for i, (img, lab) in enumerate(sources):
        split = "val" if i < n_val else "train"
        dst_img = YOLO_IMGS/split/img.name
        dst_lab = YOLO_LABS/split/lab.name
        safe_copy(img, dst_img)
        safe_copy(lab, dst_lab)

    print(f"[PREP] train: {max(0, n_total - n_val)}, val: {n_val}")
    return (max(0, n_total - n_val), n_val)

# ---------------- 4) (Optional) TRAIN ----------------


def stage_train(data_yaml: Path, model: str = "yolov8m.pt", epochs: int = 150, imgsz: int = 640, batch: int = 32):
    print("[TRAIN] Launching YOLO training via Ultralytics API")
    y = YOLO(model)
    y.train(data=str(data_yaml), epochs=epochs, imgsz=imgsz,
            batch=batch, workers=os.cpu_count())

# ---------------- CLI ----------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true", help="Run ingest stage")
    ap.add_argument("--select", action="store_true",
                    help="Run selection (active learning) stage")
    ap.add_argument("--prep", action="store_true",
                    help="Prepare YOLO dataset (train/val split)")
    ap.add_argument("--train", action="store_true",
                    help="Train a YOLO model after prep")
    ap.add_argument("--all", action="store_true",
                    help="Run all stages (ingest+select+prep)")
    ap.add_argument("--model", type=str, default="./models/hydration_model.pt",
                    help="Path to your trained weights")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf_low", type=float, default=0.15,
                    help="<= this = low confidence")
    ap.add_argument("--conf_high", type=float, default=0.45,
                    help="(low, high] = mid confidence")
    ap.add_argument("--val_split", type=float, default=0.15,
                    help="validation fraction")
    ap.add_argument("--data_yaml", type=str,
                    default="./data/hydration_data.yaml")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    ensure_dirs()

    if args.all:
        stage_ingest()
        stage_select(Path(args.model), args.imgsz,
                     args.conf_low, args.conf_high)
        stage_prep(args.val_split)
    else:
        if args.ingest:
            stage_ingest()
        if args.select:
            stage_select(Path(args.model), args.imgsz,
                         args.conf_low, args.conf_high)
        if args.prep:
            stage_prep(args.val_split)

    if args.train:
        stage_train(Path(args.data_yaml), model="yolov8m.pt",
                    epochs=args.epochs, imgsz=args.imgsz, batch=args.batch)


if __name__ == "__main__":
    main()


