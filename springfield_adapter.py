# File: scripts/springfield_adapter.py
import time, json, requests, os
from datetime import datetime
import cv2
import numpy as np

# Try to use ultralytics YOLO if available
try:
    from ultralytics import YOLO
    ULTRALYTICS = True
except Exception:
    ULTRALYTICS = False

MODEL_PATH = os.path.join("static", "models", "hydration_model.pt")  # your model
CLASS_NAMES = ["grass", "dead_grass", "puddle", "standing_water"]  # replace with your classes
POST_URL = os.environ.get("II_POST_URL", "http://127.0.0.1:5051/api/hydration")
CAMERA_SRC = int(os.environ.get("II_CAMERA_SRC", "0"))  # or path to video

def make_payload(green_coverage, detections, extra=None):
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "green_coverage": float(green_coverage),
        "dead_grass_pct": float(extra.get("dead_grass_pct", 0.0)) if extra else 0.0,
        "standing_water": any(d["class"] == "standing_water" for d in detections),
        "puddles_conf": max((d["conf"] for d in detections if d["class"] == "puddle"), default=0.0),
        "detections": detections
    }

def compute_green_ratio(frame_bgr):
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 40, 40], dtype=np.uint8)
    upper = np.array([85, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return float(np.count_nonzero(mask)) / mask.size

def detect_with_ultralytics(frame):
    model = YOLO(MODEL_PATH)
    # run one-shot detection; tune params to your model
    results = model.predict(source=frame, imgsz=640, conf=0.35, half=False, device='cpu')
    # assuming results[0] exists
    r = results[0]
    detections = []
    for box, cls, conf in zip(r.boxes.xyxy.tolist() if hasattr(r, 'boxes') else [], r.boxes.cls.tolist() if hasattr(r, 'boxes') else [], r.boxes.conf.tolist() if hasattr(r, 'boxes') else []):
        cls = int(cls)
        detections.append({"class": CLASS_NAMES[cls] if cls < len(CLASS_NAMES) else str(cls), "conf": float(conf), "bbox": box})
    return detections

def main_loop():
    cap = cv2.VideoCapture(CAMERA_SRC)
    if not cap.isOpened():
        print("camera open failed for", CAMERA_SRC)
        return
    print("Started adapter loop, posting to", POST_URL)
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.5)
            continue
        green = compute_green_ratio(frame)
        # replace with your model inference function if not ultralytics
        detections = []
        if ULTRALYTICS:
            try:
                detections = detect_with_ultralytics(frame)
            except Exception as e:
                print("model inference error:", e)
        payload = make_payload(green, detections)
        try:
            r = requests.post(POST_URL, json=payload, timeout=3.0)
            print("POST", r.status_code, r.text)
        except Exception as e:
            print("POST failed:", e)
        time.sleep(1.0)  # adjust cadence
    cap.release()

if __name__ == "__main__":
    main_loop()
