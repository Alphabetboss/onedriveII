#!/usr/bin/env python3
"""
make_report.py â€” Build an HTML dashboard of your dataset balance and latest YOLO results.

It looks for:
- Dataset: .\dataset\yolo\images\train, val AND labels\train, val
- YOLO results: .\runs\detect\train*\results.csv (latest)

Outputs:
- reports\index.html
- reports\class_balance.png
- reports\metrics.png  (if results.csv found)
"""

from __future__ import annotations
import argparse
import csv
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

CLASSES = [
    "healthy_grass", "dry_grass", "water", "standing_water",
    "mud", "mushy_grass", "leak", "sprinkler"
]


def count_labels(label_dir: Path) -> Dict[str, int]:
    counts = {c: 0 for c in CLASSES}
    if not label_dir.exists():
        return counts
    for txt in label_dir.glob("*.txt"):
        for line in txt.read_text().strip().splitlines():
            if not line.strip():
                continue
            cid = int(line.split()[0])
            if 0 <= cid < len(CLASSES):
                counts[CLASSES[cid]] += 1
    return counts


def latest_results_csv(runs_dir: Path) -> Path | None:
    if not runs_dir.exists():
        return None
    candidates = sorted(runs_dir.glob("train*/results.csv"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def read_results_csv(p: Path) -> Dict[str, List[float]]:
    rows = list(csv.DictReader(p.open()))
    # Return series for common keys if present
    keys = ["                   metrics/precision(B)", "                   metrics/recall(B)", "                   metrics/mAP50(B)", "                   metrics/mAP50-95(B)",
            "                  train/box_loss", "                  train/cls_loss", "                  val/box_loss", "                  val/cls_loss"]
    # Normalize keys (ultralytics sometimes pads with spaces)
    norm = {}
    for k in keys:
        for col in rows[0].keys():
            if col.strip() == k.strip():
                norm[k] = col
                break
    out = {k.strip(): [] for k in norm}
    for r in rows:
        for k, col in norm.items():
            try:
                out[k.strip()].append(float(r[col]))
            except Exception:
                pass
    return out


def save_bar_chart(train_counts: Dict[str, int], val_counts: Dict[str, int], out_png: Path):
    labels = CLASSES
    train = [train_counts.get(c, 0) for c in labels]
    val = [val_counts.get(c, 0) for c in labels]

    plt.figure(figsize=(10, 4))
    x = range(len(labels))
    plt.bar(x, train, label="train")
    plt.bar(x, val, bottom=train, label="val")
    plt.xticks(list(x), labels, rotation=25, ha="right")
    plt.ylabel("instances")
    plt.title("Class Balance (train + val)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


def save_metrics_plot(metrics: Dict[str, List[float]], out_png: Path):
    if not metrics:
        return
    plt.figure(figsize=(10, 4))
    for k, series in metrics.items():
        plt.plot(series, label=k)
    plt.xlabel("epoch")
    plt.title("Training Metrics")
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


def write_html(report_dir: Path, class_png: Path, metrics_png: Path | None, notes: Dict[str, str]):
    html = ["<html><head><meta charset='utf-8'><title>Ingenious Irrigation â€” Training Report</title>",
            "<style>body{font-family:Segoe UI,Arial;margin:20px;color:#e6f2e6;background:#0b0c0c} .card{background:#1c1f22;padding:16px;border-radius:12px;margin-bottom:16px} h1,h2{color:#92ff7a}</style>",
            "</head><body>",
            "<h1>Ingenious Irrigation â€” Training Report</h1>",
            "<div class='card'><h2>Class Balance</h2>",
            f"<img src='{class_png.name}' style='max-width:100%'></div>"]
    if metrics_png and metrics_png.exists():
        html += ["<div class='card'><h2>Training Metrics</h2>",
                 f"<img src='{metrics_png.name}' style='max-width:100%'></div>"]
    html += ["<div class='card'><h2>Notes</h2><ul>"]
    for k, v in notes.items():
        html += [f"<li><b>{k}:</b> {v}</li>"]
    html += ["</ul></div></body></html>"]
    (report_dir / "index.html").write_text("\n".join(html), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo_dir", type=str, default="./dataset/yolo")
    ap.add_argument("--runs_dir", type=str, default="./runs/detect")
    ap.add_argument("--out", type=str, default="./reports")
    args = ap.parse_args()

    yolo = Path(args.yolo_dir)
    runs = Path(args.runs_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Count classes
    tr_counts = count_labels(yolo / "labels" / "train")
    va_counts = count_labels(yolo / "labels" / "val")
    class_png = out / "class_balance.png"
    save_bar_chart(tr_counts, va_counts, class_png)

    # Read latest results
    rcsv = latest_results_csv(runs)
    metrics_png = out / "metrics.png"
    notes = {"runs_dir": str(runs.resolve()),
             "latest_results_csv": str(rcsv.resolve()) if rcsv else "not found"}

    if rcsv and rcsv.exists():
        m = read_results_csv(rcsv)
        save_metrics_plot(m, metrics_png)
    else:
        metrics_png = None

    write_html(out, class_png, metrics_png, notes)
    print(f"[report] Wrote {out / 'index.html'}")


if __name__ == "__main__":
    main()