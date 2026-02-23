# health_api.py
from flask import Flask, jsonify
import requests
import cv2
from pathlib import Path
from health_detector import YoloV8ONNX
import os

CAMERA_BASE = os.getenv("II_CAMERA_BASE", "http://127.0.0.1:5051")
app = Flask(__name__)
yolo = YoloV8ONNX()  # loads model once


@app.get("/analyze_live")
def analyze_live():
    try:
        r = requests.get(f"{CAMERA_BASE}/snapshot",
                         params={"label": "analyze"}, timeout=5)
        r.raise_for_status()
        p = r.json().get("path")
        if not p or not Path(p).exists():
            return jsonify({"ok": False, "error": "no snapshot path"}), 500
        img = cv2.imread(p)
        res = yolo.infer(img)
        return jsonify({"ok": True, **res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/")
def root():
    return "Ingenious Irrigation â€” health_api up. GET /analyze_live"


if __name__ == "__main__":
    app.run(port=5053, debug=True)