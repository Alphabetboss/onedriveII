# flask_camera_api.py
from flask import Flask, jsonify, send_file, Response
import cv2
import io
import time
from green_detector import pct_green_from_bgr_image, hydration_need_from_green_frac, visualize_mask_on_image
import numpy as np

app = Flask(__name__)
CAM_INDEX = 0
CAPTURE_WIDTH = 1280
CAPTURE_HEIGHT = 720

def capture_frame():
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if ok:
            cap.release()
            return frame
        if time.time() - t0 > 5.0:
            cap.release()
            raise RuntimeError("Camera capture timeout")

@app.route("/hydration")
def hydration():
    try:
        frame = capture_frame()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    green_frac, mask = pct_green_from_bgr_image(frame)
    score = hydration_need_from_green_frac(green_frac)
    # return JSON
    return jsonify({
        "green_fraction": round(green_frac, 4),
        "hydration_need": round(score, 2),  # 0..10 (inverted)
        "timestamp": int(time.time())
    })

@app.route("/snapshot")
def snapshot():
    # return overlayed debug JPEG
    try:
        frame = capture_frame()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    green_frac, mask = pct_green_from_bgr_image(frame)
    vis = visualize_mask_on_image(frame, mask, alpha=0.6)

    # encode JPEG
    ok, buf = cv2.imencode('.jpg', vis)
    if not ok:
        return jsonify({"error": "failed to encode image"}), 500
    return Response(buf.tobytes(), mimetype='image/jpeg')

if __name__ == "__main__":
    # dev server for initial testing
    app.run(host="0.0.0.0", port=5001, debug=True)
