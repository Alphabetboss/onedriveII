#!/usr/bin/env python3
"""
rf_upload.py â€” Zip & upload your 'dataset/to_label' images to Roboflow.

Usage (PowerShell):
python .\rf_upload.py --src .\dataset\to_label --workspace <w> --project <p> --version 1
(Will read ROBOFLOW_API_KEY from env by default.)
"""

from __future__ import annotations
import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import List

from roboflow import Roboflow

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def chunk_paths(paths: List[Path], size: int = 800):
    for i in range(0, len(paths), size):
        yield paths[i:i+size]


def zip_chunk(files: List[Path], zip_dir: Path) -> Path:
    tmp = tempfile.mkdtemp()
    tmpd = Path(tmp)
    imgdir = tmpd / "images"
    imgdir.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, imgdir / p.name)
    zip_path = zip_dir / f"rf_upload_{int(time.time())}_{len(files)}.zip"
    shutil.make_archive(str(zip_path).replace(".zip", ""), 'zip', str(tmpd))
    shutil.rmtree(tmpd, ignore_errors=True)
    return zip_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=str, default="./dataset/to_label")
    ap.add_argument("--workspace", type=str,
                    default=os.getenv("ROBOFLOW_WORKSPACE"))
    ap.add_argument("--project", type=str,
                    default=os.getenv("ROBOFLOW_PROJECT"))
    ap.add_argument("--version", type=str,
                    default=os.getenv("ROBOFLOW_VERSION", "1"))
    ap.add_argument("--api_key", type=str,
                    default=os.getenv("ROBOFLOW_API_KEY"))
    ap.add_argument("--batch", type=int, default=800,
                    help="images per upload zip")
    args = ap.parse_args()

    if not args.api_key:
        raise SystemExit(
            "ROBOFLOW_API_KEY missing. Set env or pass --api_key.")

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"Source not found: {src}")

    files = [p for p in src.glob("*") if p.suffix.lower() in IMAGE_EXTS]
    if not files:
        print("[rf_upload] Nothing to upload in to_label.")
        return

    rf = Roboflow(api_key=args.api_key)
    project = rf.workspace(args.workspace).project(args.project)
    version = project.version(args.version)

    zip_dir = Path("pipeline_runs") / "roboflow_zips"
    zip_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for chunk in chunk_paths(files, size=args.batch):
        z = zip_chunk(chunk, zip_dir)
        print(f"[rf_upload] Uploading {len(chunk)} images via {z.name} ...")
        # Roboflow auto-detects unzip; this associates to the version for labeling
        version.upload(str(z))
        total += len(chunk)

    print(
        f"[rf_upload] Uploaded {total} images to {args.workspace}/{args.project}/{args.version}")
    print("Tip: Label in Roboflow, export YOLOv8, and drop labeled images+txts in .\\dataset\\labeled")


if __name__ == "__main__":
    main()