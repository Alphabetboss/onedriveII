# irrigation_api.py
import os
import io
import json
import time
import datetime as dt
from pathlib import Path
from typing import Dict, Any

# _YOLO = None
# _YOLO_ERROR = None
# 
# 
# def _load_yolo():
#     global _YOLO, _YOLO_ERROR
#     if _YOLO is not None or _YOLO_ERROR:
#         return _YOLO
#     try:
#         from ultralytics import YOLO
#         print(f"[hydration] Loading YOLO weights: {YOLO_WEIGHTS}")
#         _YOLO = YOLO(YOLO_WEIGHTS)
#         print("[hydration] YOLO loaded. Classes:", _YOLO.names)
#     except Exception as e:
#         _YOLO_ERROR = e
#         print("[hydration] YOLO load failed, falling back to HSV method:", repr(e))
#     return _YOLO
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image
import cv2

# ---- Try to use your real schedule manager; stub if missing ----
import importlib
_schedule_module = None
try:
    _schedule_module = importlib.import_module("schedule_manager")
except Exception:
    _schedule_module = None

if _schedule_module is not None:
    start_watering = getattr(_schedule_module, "start_watering")
    stop_watering = getattr(_schedule_module, "stop_watering")
    get_status = getattr(_schedule_module, "get_status")
    skip_next_run = getattr(_schedule_module, "skip_next_run")
    resume_schedule = getattr(_schedule_module, "resume_schedule")
    set_zone_duration = getattr(_schedule_module, "set_zone_duration")
else:
    _current = {"watering": False, "active_zone": None, "minutes": 0}
    def start_watering(zone=1, minutes=None):
        _current.update({"watering": True, "active_zone": zone, "minutes": int(minutes or 0)})
        return True
    def stop_watering():
        _current.update({"watering": False, "active_zone": None, "minutes": 0})
        return True
    def get_status():
        return dict(_current)
    def skip_next_run():
        return True
    def resume_schedule():
        return True
    def set_zone_duration(zone:int, minutes:int):
        _current.update({"active_zone": zone, "minutes": int(minutes)})
        return True
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"; DATA_DIR.mkdir(exist_ok=True)
UPLOADS = ROOT / "uploads"; UPLOADS.mkdir(exist_ok=True)
LOG = DATA_DIR / "hydration_log.jsonl"
API_KEY = os.getenv("II_API_KEY", "dev-key")
app = Flask(__name__, static_folder="static", template_folder="templates")

def authed() -> bool:
    return request.headers.get("X-API-Key", "") == API_KEY

# =================== YOLOv8 hydration (with safe fallback) ===================
from ultralytics import YOLO
_YOLO = None
_YOLO_ERROR = None
YOLO_WEIGHTS = os.getenv("II_YOLO_WEIGHTS", str((ROOT / "models" / "ingenious_yolov8.pt").resolve()))
def _load_yolo():
    """Load YOLO weights once; remember failure so we can fall back."""
    global _YOLO, _YOLO_ERROR
    if _YOLO is not None or _YOLO_ERROR:
        return _YOLO
    try:
        print(f"[hydration] Loading YOLO weights: {YOLO_WEIGHTS}")
        _YOLO = YOLO(YOLO_WEIGHTS)
        print("[hydration] YOLO loaded. Classes:", _YOLO.names)
    except Exception as e:
        _YOLO_ERROR = e
        print("[hydration] YOLO load failed, falling back to HSV method:", repr(e))
    return _YOLO

def bgr_to_hydration(img_bgr: np.ndarray) -> Dict[str, Any]:
    """Return hydration state (0â€“10) plus class ratios."""
    # Try YOLO first
    model = _load_yolo()
    if model is not None:
        try:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            res = model.predict(img_rgb, imgsz=640, conf=0.25, verbose=False)[0]
            names = res.names  # {id: "class_name"}
            H, W = img_rgb.shape[:2]
            total_pixels = float(H * W)

            masks = getattr(res, "masks", None)
            boxes = getattr(res, "boxes", []) or []
            grass_area = water_area = dead_area = 0.0

            # If masks are present and have .data, iterate masks paired with boxes,
            # otherwise fall back to using box coordinates only. Use safe defaults
            # so we never attempt to iterate over None.
            if masks is not None and getattr(masks, "data", None) is not None:
                for mask, box in zip(masks.data, boxes):
                    cls = int(box.cls[0].item()); cname = names.get(cls, "")
                    pixels = float(mask.sum().item())
                    if cname == "grass": grass_area += pixels
                    elif cname == "water": water_area += pixels
                    elif cname in ("dead_grass", "dead-grass", "dead grass"): dead_area += pixels
            else:
                for box in boxes:
                    cls = int(box.cls[0].item()); cname = names.get(cls, "")
                    x1,y1,x2,y2 = box.xyxy[0].tolist()
                    area = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))
                    if cname == "grass": grass_area += area
                    elif cname == "water": water_area += area
                    elif cname in ("dead_grass", "dead-grass", "dead grass"): dead_area += area

            green_ratio = float(min(1.0, grass_area / total_pixels))
            water_ratio = float(min(1.0, water_area / total_pixels))
            dead_ratio  = float(min(1.0, dead_area  / total_pixels))

            baseline = np.interp(green_ratio, [0.05, 0.30, 0.60], [1.0, 5.0, 8.0])
            penalty  = np.interp(dead_ratio,  [0.00, 0.10, 0.30], [0.0,  1.0, 2.5])
            hydration = baseline - penalty
            if water_ratio >= 0.03:
                hydration = max(hydration, 9.0 + min(1.0, (water_ratio - 0.03) * 30))  # 9..10

            hydration = float(round(np.clip(hydration, 0, 10), 2))
            return {
                "hydration": hydration,
                "green_ratio": round(green_ratio, 4),
                "water_ratio": round(water_ratio, 4),
                "dead_ratio":  round(dead_ratio,  4),
                "backend": "yolov8"
            }
        except Exception as e:
            print("[hydration] YOLO inference failed; falling back. Error:", repr(e))

    # --------------------- Fallback: HSV greenness method ---------------------
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    green_low  = np.array([35, 60, 40], dtype=np.uint8)
    green_high = np.array([85, 255, 255], dtype=np.uint8)
    green_mask = cv2.inRange(hsv, green_low, green_high)

    blue_low  = np.array([90, 40, 40], dtype=np.uint8)
    blue_high = np.array([140, 255, 255], dtype=np.uint8)
    blue_mask = cv2.inRange(hsv, blue_low, blue_high)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    dark_mask = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)[1]

    total = img_bgr.shape[0] * img_bgr.shape[1]
    green_ratio = float(np.count_nonzero(green_mask)) / total
    water_ratio = float(np.count_nonzero(cv2.bitwise_or(blue_mask, dark_mask))) / total

    hydration = np.interp(green_ratio, [0.10, 0.35, 0.70], [0.0, 5.0, 8.0])
    if water_ratio >= 0.06:
        hydration = max(hydration, 9.0 + min(1.0, (water_ratio - 0.06) * 20))
    hydration = float(round(np.clip(hydration, 0, 10), 2))

    return {
        "hydration": hydration,
        "green_ratio": round(green_ratio, 4),
        "water_ratio": round(water_ratio, 4),
        "backend": "hsv"
    }

# ============================ Logging helpers ============================
def log_hydration(entry: Dict[str, Any]) -> None:
    entry = dict(entry)
    entry["ts"] = dt.datetime.utcnow().isoformat() + "Z"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def tail_log(n=200):
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in lines if x.strip()]

# =============================== Web UI ===============================
@app.get("/")
def home():
    return render_template("index.html")

# ============================ Irrigation API ============================
@app.post("/api/irrigation/start")
def api_start():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    ok = start_watering(zone=1)
    return jsonify({"ok": bool(ok)})
@app.post("/api/irrigation/stop")
def api_stop():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    ok = stop_watering()
    return jsonify({"ok": bool(ok)})
@app.get("/api/irrigation/status")
def api_status():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_status())
@app.post("/api/irrigation/skip")
def api_skip():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": skip_next_run()})
@app.post("/api/irrigation/resume")
def api_resume():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": resume_schedule()})
@app.post("/api/irrigation/zone/<int:zone>/duration")
def api_set_zone_duration(zone: int):
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    minutes = int(data.get("minutes", 10))
    ok = set_zone_duration(zone=zone, minutes=minutes)
    return jsonify({"ok": bool(ok), "zone": zone, "minutes": minutes})

# ============================ Hydration API ============================
@app.post("/api/hydration/analyze")
def api_hydration_analyze():
    """Accepts multipart 'image' file or raw bytes; returns hydration."""
    if not authed():
        return jsonify({"error": "unauthorized"}), 401

    img_bytes = None
    if "image" in request.files:
        file = request.files["image"]
        fname = secure_filename(file.filename or f"upload_{int(time.time())}.png")
        raw = file.read()
        img_bytes = raw
        (UPLOADS / fname).write_bytes(raw)
    else:
        img_bytes = request.get_data()

    if not img_bytes:
        return jsonify({"error": "no image received"}), 400

    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return jsonify({"error": f"decode failed: {e}"}), 400

    res = bgr_to_hydration(img_bgr)
    log_hydration({"source": "upload", **res})
    return jsonify(res)
@app.get("/api/hydration/log")
def api_hydration_log():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(tail_log(200))

if __name__ == "__main__":
    # Tip: set II_YOLO_WEIGHTS to your .pt path if not using the default.
    app.run(host="0.0.0.0", port=5000)

