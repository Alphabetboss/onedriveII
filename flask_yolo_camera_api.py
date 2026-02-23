# flask_yolo_camera_api.py
import os
import time
import io
from typing import Tuple, Dict

import cv2
import numpy as np
from flask import Flask, jsonify, Response

# Optional: only import ultralytics if model will be used
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except Exception:
    ULTRALYTICS_AVAILABLE = False

# -------------------------
# Config - edit if needed
# -------------------------
CAM_INDEX = int(os.getenv("CAM_INDEX", "0"))
CAPTURE_WIDTH = int(os.getenv("CAPTURE_WIDTH", "1280"))
CAPTURE_HEIGHT = int(os.getenv("CAPTURE_HEIGHT", "720"))
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "best.pt")  # change to your path if different
USE_YOLO_IF_AVAILABLE = True  # will attempt YOLO if ultralytics is installed and file exists
# -------------------------

app = Flask(__name__)

# -------------------------
# Color-based detector
# -------------------------
def pct_green_from_bgr_image(bgr_image: np.ndarray) -> Tuple[float, np.ndarray]:
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    # HSV thresholds for green (tweak per camera)
    lower = np.array([30, 40, 40])
    upper = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    green_pixels = int(np.count_nonzero(mask))
    total_pixels = mask.size
    green_frac = (green_pixels / total_pixels) if total_pixels > 0 else 0.0
    return float(green_frac), mask

def visualize_mask_on_image(bgr_image: np.ndarray, mask: np.ndarray, alpha: float=0.5) -> np.ndarray:
    overlay = bgr_image.copy()
    overlay[mask > 0] = (0, 255, 0)
    return cv2.addWeighted(overlay, alpha, bgr_image, 1 - alpha, 0)

# Map fraction -> inverted 0..10 hydration_need scale
def hydration_need_from_fraction(frac: float,
                                 dry_frac: float = 0.05,
                                 optimal_frac: float = 0.30,
                                 saturated_frac: float = 0.70) -> float:
    gf = max(0.0, min(1.0, float(frac)))
    if gf <= dry_frac:
        return 0.0
    if gf >= saturated_frac:
        return 10.0
    if gf <= optimal_frac:
        return 5.0 * (gf - dry_frac) / max(1e-6, (optimal_frac - dry_frac))
    return 5.0 + 5.0 * (gf - optimal_frac) / max(1e-6, (saturated_frac - optimal_frac))

# -------------------------
# Camera capture helper
# -------------------------
def capture_frame(timeout=5.0) -> np.ndarray:
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if ok:
            cap.release()
            return frame
        if time.time() - t0 > timeout:
            cap.release()
            raise RuntimeError("Camera capture timeout")

# -------------------------
# YOLO model loader (lazy)
# -------------------------
_model = None
_model_names = {}
def load_yolo_model():
    global _model, _model_names
    if _model is not None:
        return _model
    if not ULTRALYTICS_AVAILABLE:
        raise RuntimeError("ultralytics is not installed")
    if not os.path.isfile(MODEL_PATH):
        raise RuntimeError(f"Model file not found at {MODEL_PATH}")
    # load model (CPU). If you want GPU on Pi with Coral, you'd change this.
    _model = YOLO(MODEL_PATH)
    # names mapping
    try:
        _model_names = _model.names
    except Exception:
        _model_names = {}
    return _model

def run_yolo_inference(frame: np.ndarray, conf=0.25, iou=0.45) -> Dict:
    """
    Returns dict with: areas_by_label (pixel area), boxes (list), names mapping
    """
    model = load_yolo_model()
    results = model(frame, conf=conf, iou=iou)[0]  # take first (single) result
    h, w = frame.shape[:2]
    areas = {}
    boxes = []
    # results.boxes may be empty
    try:
        xyxy = results.boxes.xyxy.cpu().numpy()  # N x 4
        cls_inds = results.boxes.cls.cpu().numpy().astype(int)  # N
        confs = results.boxes.conf.cpu().numpy()
    except Exception:
        # fallback if APIs differ
        xyxy = []
        cls_inds = []
        confs = []

    for idx, box in enumerate(xyxy):
        x1, y1, x2, y2 = box[:4]
        area = max(0, (x2 - x1) * (y2 - y1))
        cls_i = int(cls_inds[idx]) if len(cls_inds) > idx else -1
        label = str(_model_names.get(cls_i, cls_i))
        areas[label] = areas.get(label, 0.0) + area
        boxes.append({
            "label": label,
            "conf": float(confs[idx]) if len(confs) > idx else None,
            "xyxy": [float(x1), float(y1), float(x2), float(y2)]
        })
    return {"areas": areas, "boxes": boxes, "img_shape": (h, w)}

# -------------------------
# Flask endpoints
# -------------------------
@app.route("/hydration")
def hydration():
    # capture frame
    try:
        frame = capture_frame()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Try YOLO first if available & configured
    yolo_result = None
    grass_frac_yolo = None
    yolo_ok = False
    if USE_YOLO_IF_AVAILABLE and ULTRALYTICS_AVAILABLE and os.path.isfile(MODEL_PATH):
        try:
            load_yolo_model()
            yres = run_yolo_inference(frame)
            yolo_result = yres
            h, w = yres["img_shape"]
            total_area = max(1, w * h)
            grass_area = float(yres["areas"].get("grass", 0.0))
            grass_frac_yolo = grass_area / total_area
            yolo_ok = True
        except Exception as e:
            # model failed — set yolo_ok False and fall back to color
            yolo_result = {"error": str(e)}

    # Color-based fallback/parallel
    green_frac_color, mask = pct_green_from_bgr_image(frame)

    # Decide which fraction to use for final hydration_need:
    # Prefer YOLO grass_frac if available; else use color-based green_frac
    chosen_frac = grass_frac_yolo if (grass_frac_yolo is not None and yolo_ok) else green_frac_color
    hydration_score = hydration_need_from_fraction(chosen_frac)

    resp = {
        "timestamp": int(time.time()),
        "chosen_fraction": round(float(chosen_frac), 5),
        "hydration_need": round(float(hydration_score), 2),
        "color": {
            "green_fraction": round(float(green_frac_color), 5)
        },
        "yolo": None
    }
    if yolo_result is not None:
        # include minimal YOLO detail
        resp["yolo"] = {
            "ok": yolo_ok,
            "info": yolo_result if not yolo_ok else {
                "areas": {k: round(float(v), 1) for k, v in (yolo_result.get("areas") or {}).items()},
                "boxes_count": len(yolo_result.get("boxes", []))
            }
        }
    return jsonify(resp)

@app.route("/snapshot")
def snapshot():
    try:
        frame = capture_frame()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    overlay = None
    # prefer YOLO overlay if possible
    if USE_YOLO_IF_AVAILABLE and ULTRALYTICS_AVAILABLE and os.path.isfile(MODEL_PATH):
        try:
            load_yolo_model()
            yres = run_yolo_inference(frame)
            overlay = frame.copy()
            for b in yres.get("boxes", []):
                x1, y1, x2, y2 = map(int, b["xyxy"])
                label = b.get("label", "obj")
                conf = b.get("conf", None)
                # draw box and label
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (0,255,0), 2)
                txt = f"{label}{'' if conf is None else (':' + str(round(conf, 2)))}"
                cv2.putText(overlay, txt, (x1, max(10, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        except Exception:
            overlay = None

    if overlay is None:
        # fallback to mask overlay
        green_frac_color, mask = pct_green_from_bgr_image(frame)
        overlay = visualize_mask_on_image(frame, mask, alpha=0.6)

    ok, buf = cv2.imencode('.jpg', overlay)
    if not ok:
        return jsonify({"error": "failed to encode image"}), 500
    return Response(buf.tobytes(), mimetype='image/jpeg')

if __name__ == "__main__":
    # dev server
    app.run(host="0.0.0.0", port=5001, debug=True)
