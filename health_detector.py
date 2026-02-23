# health_detector.py
# YOLOv8-ONNX inference + hydration score
from __future__ import annotations
import os
import math
import time
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
import cv2
import onnxruntime as ort

# -------- Config --------
MODEL_PATH = Path("yolov8n.onnx")            # change if different
CLASSES_PATH = Path("data/models/classes.txt")
IMG_SIZE = 640
CONF_THRES = 0.25
IOU_THRES = 0.45
PROVIDERS = ["CPUExecutionProvider"]        # set to CUDA if you have it
# ------------------------


def load_classes(path: Path) -> List[str]:
    if path.exists():
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Fallback minimal set
    return ["grass", "water", "dead_grass"]


def letterbox(im: np.ndarray, new_shape=IMG_SIZE, color=(114, 114, 114)) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    h, w = im.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right,
                            cv2.BORDER_CONSTANT, value=color)
    return im, r, (left, top)


def xywh2xyxy(x):
    y = np.zeros_like(x)
    y[:, 0] = x[:, 0] - x[:, 2]/2
    y[:, 1] = x[:, 1] - x[:, 3]/2
    y[:, 2] = x[:, 0] + x[:, 2]/2
    y[:, 3] = x[:, 1] + x[:, 3]/2
    return y


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thres=0.45) -> List[int]:
    # class-agnostic NMS
    idxs = scores.argsort()[::-1]
    keep = []
    while idxs.size > 0:
        i = idxs[0]
        keep.append(i)
        if idxs.size == 1:
            break
        ious = iou(boxes[i], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_thres]
    return keep


def iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    inter = (np.minimum(boxes[:, 2], box[2]) - np.maximum(boxes[:, 0], box[0])).clip(0) * \
            (np.minimum(boxes[:, 3], box[3]) -
             np.maximum(boxes[:, 1], box[1])).clip(0)
    area1 = (box[2]-box[0]) * (box[3]-box[1])
    area2 = (boxes[:, 2]-boxes[:, 0]) * (boxes[:, 3]-boxes[:, 1])
    return inter / (area1 + area2 - inter + 1e-6)


class YoloV8ONNX:
    def __init__(self, model_path=MODEL_PATH, providers=PROVIDERS):
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        self.sess = ort.InferenceSession(str(model_path), providers=providers)
        self.inp_name = self.sess.get_inputs()[0].name
        self.classes = load_classes(CLASSES_PATH)

    def infer(self, img_bgr: np.ndarray,
              conf_thres=CONF_THRES, iou_thres=IOU_THRES) -> Dict:
        orig = img_bgr.copy()
        h0, w0 = orig.shape[:2]

        # Preprocess
        img, r, (dw, dh) = letterbox(orig, IMG_SIZE)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = (img.astype(np.float32) /
               255.0).transpose(2, 0, 1)[None]  # 1x3xHxW

        # Inference
        out = self.sess.run(None, {self.inp_name: img})[
            0]  # shape (1, no, N) or (1, N, no)
        pred = np.squeeze(out, 0)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T  # (N, no)
        boxes_xywh = pred[:, :4]
        scores_per_class = pred[:, 4:]

        # Best class per candidate
        class_ids = scores_per_class.argmax(1)
        scores = scores_per_class.max(1)

        # Filter by confidence
        m = scores >= conf_thres
        boxes_xywh = boxes_xywh[m]
        scores = scores[m]
        class_ids = class_ids[m]

        if boxes_xywh.size == 0:
            return {"detections": [], "hydration_score": 5.0, "meta": {"w": w0, "h": h0}}

        # Convert & scale back to original image
        boxes = xywh2xyxy(boxes_xywh)
        # undo letterbox
        boxes[:, [0, 2]] -= dw
        boxes[:, [1, 3]] -= dh
        boxes /= r
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w0)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h0)

        # NMS
        keep = nms(boxes, scores, iou_thres)
        boxes, scores, class_ids = boxes[keep], scores[keep], class_ids[keep]

        # Build detections
        dets = []
        for box, sc, cid in zip(boxes, scores, class_ids):
            x1, y1, x2, y2 = box.tolist()
            cname = self.classes[int(cid)] if int(cid) < len(
                self.classes) else f"class_{int(cid)}"
            dets.append({
                "class_id": int(cid),
                "class_name": cname,
                "confidence": float(sc),
                "box_xyxy": [float(x1), float(y1), float(x2), float(y2)]
            })

        score = hydration_score(dets, (w0, h0))
        return {"detections": dets, "hydration_score": score, "meta": {"w": w0, "h": h0}}


def hydration_score(dets: List[Dict], size: Tuple[int, int]) -> float:
    """Return 0â€“10 (0=dry, 5=ok, 10=oversaturated). Uses area fractions per class."""
    w, h = size
    area = w * h + 1e-6

    # Buckets (rename here to match your labels)
    water_like = {"water", "standing_water", "mushy_grass", "mud"}
    dry_like = {"dead_grass", "dry_soil", "brown_patch"}
    healthy_like = {"grass", "healthy_grass", "green_grass"}

    frac = {"water": 0.0, "dry": 0.0, "healthy": 0.0}
    confs = []

    for d in dets:
        x1, y1, x2, y2 = d["box_xyxy"]
        a = max(0.0, (x2-x1)) * max(0.0, (y2-y1)) / area
        name = d["class_name"]
        c = d["confidence"]
        confs.append(c)
        if name in water_like:
            frac["water"] += a
        if name in dry_like:
            frac["dry"] += a
        if name in healthy_like:
            frac["healthy"] += a

    # Simple weighted blend â†’ clamp to [0,10]
    mean_conf = float(np.mean(confs)) if confs else 0.5
    sat = (0.60*frac["water"] + 0.20*frac["healthy"] -
           0.50*frac["dry"] + 0.10*mean_conf)
    score = max(0.0, min(10.0, 10.0 * sat))
    # Bias towards mid if nothing conclusive
    if not dets:
        score = 5.0
    return float(score)


# CLI test:
if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Path to image for testing")
    ap.add_argument("--out", default="outputs/annotated.jpg")
    args = ap.parse_args()

    Path("outputs").mkdir(exist_ok=True)
    img = cv2.imread(args.image)
    yolo = YoloV8ONNX()
    res = yolo.infer(img)
    print(json.dumps({"hydration_score": res["hydration_score"], "n": len(
        res["detections"])}, indent=2))

    # annotate and save
    for d in res["detections"]:
        x1, y1, x2, y2 = map(int, d["box_xyxy"])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, f"{d['class_name']} {d['confidence']:.2f}", (x1, max(15, y1-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.imwrite(args.out, img)
    print(f"Saved {args.out}")