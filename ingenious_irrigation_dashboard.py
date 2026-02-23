from flask import Flask, render_template, jsonify
import os
import base64
import cv2
import requests
from pathlib import Path
from health_detector import YoloV8ONNX

app = Flask(__name__, template_folder="templates", static_folder="static")

CAMERA_BASE = os.getenv("II_CAMERA_BASE", "http://127.0.0.1:5051")
yolo = YoloV8ONNX()  # loads your yolov8n.onnx once


@app.route("/")
def dashboard():
    return render_template("dashboard.html", camera_url=f"{CAMERA_BASE}/video")


@app.get("/api/analyze_live")
def analyze_live():
    try:
        r = requests.get(f"{CAMERA_BASE}/snapshot",
                         params={"label": "analyze"}, timeout=5)
        r.raise_for_status()
        p = r.json().get("path")
        if not p or not Path(p).exists():
            return jsonify({"ok": False, "error": "no snapshot"}), 500
        img = cv2.imread(p)
        res = yolo.infer(img)
        ok, buf = cv2.imencode(".jpg", img)
        b64 = base64.b64encode(buf).decode("ascii") if ok else ""
        return jsonify({"ok": True, **res, "image_b64": "data:image/jpeg;base64," + b64})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5050, debug=True)