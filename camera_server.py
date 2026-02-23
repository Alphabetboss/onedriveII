import os
import sys
import cv2
import platform
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, request, jsonify
from ii_config import CAMERA_INDEX, ZONE_COUNT, LOG_FILE

# -------- Settings --------
PORT = int(os.getenv("II_CAMERA_PORT", "5051"))
# Try these indices in order; can override via env II_CAMERA_INDEX="1,0,2"
PREFERRED = [int(x) for x in os.getenv("II_CAMERA_INDEX",
                                       "0,1,2,3").split(",") if x.strip().isdigit()]
RES_CHOICES = [(1280, 720), (1920, 1080), (640, 480)]
SNAP_DIR = Path("data/camera_snapshots")
SNAP_DIR.mkdir(parents=True, exist_ok=True)

IS_WIN = platform.system() == "Windows"
BACKENDS = [cv2.CAP_DSHOW, cv2.CAP_MSMF,
            cv2.CAP_ANY] if IS_WIN else [cv2.CAP_ANY]
# -------------------------

app = Flask(__name__)

cap = None
current_index = None
cap_lock = threading.Lock()


def _try_open(index: int):
    """Open a camera index, try multiple backends on Windows, set resolution, validate with a read."""
    for backend in BACKENDS:
        c = cv2.VideoCapture(index, backend)
        if not c.isOpened():
            c.release()
            continue
        # Set a good resolution if possible
        for (w, h) in RES_CHOICES:
            c.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            c.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        ok, frame = c.read()
        if ok and frame is not None:
            return c
        c.release()
    return None


def _open_first_available():
    global cap, current_index
    for idx in PREFERRED:
        c = _try_open(idx)
        if c:
            cap = c
            current_index = idx
            print(f"[camera] Using camera index {idx}")
            return True
    print("[camera] No working camera found among:", PREFERRED)
    return False


def _ensure_camera():
    """Ensure we have an open camera; reopen if needed."""
    global cap
    with cap_lock:
        if cap is None or not cap.isOpened():
            _open_first_available()


def _read_frame():
    """Read a frame; if it fails, try to reopen once."""
    global cap
    with cap_lock:
        if cap is None:
            return None
        ok, frame = cap.read()
        if ok and frame is not None:
            return frame
        # attempt one reopen on same index
        idx = current_index
        if idx is not None:
            if cap:
                cap.release()
            newc = _try_open(idx)
            if newc:
                cap = newc
                ok2, frame2 = cap.read()
                if ok2 and frame2 is not None:
                    return frame2
        return None


@app.route("/video")
def video():
    def gen():
        miss = 0
        while True:
            frame = _read_frame()
            if frame is None:
                miss += 1
                if miss > 30:
                    _ensure_camera()
                    miss = 0
                continue
            miss = 0
            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
    _ensure_camera()
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/snapshot")
def snapshot():
    label = request.args.get("label", "unlabeled")
    _ensure_camera()
    frame = _read_frame()
    if frame is None:
        return jsonify({"ok": False, "error": "camera read failed"}), 500
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = SNAP_DIR / label
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ts}.jpg"
    cv2.imwrite(str(path), frame)
    return jsonify({"ok": True, "path": str(path), "index": current_index})


@app.route("/probe")
def probe():
    """Probe indices to find which can open & read one frame."""
    indices = [int(x) for x in request.args.get("indices", ",".join(
        map(str, PREFERRED))).split(",") if x.strip().isdigit()]
    found = []
    for idx in indices:
        c = _try_open(idx)
        if c:
            c.release()
            found.append(idx)
    return jsonify({"ok": True, "working_indices": found})


@app.route("/switch")
def switch():
    """Switch to a different camera index at runtime: /switch?index=1"""
    global cap, current_index
    try:
        idx = int(request.args.get("index", "-1"))
    except ValueError:
        return jsonify({"ok": False, "error": "invalid index"}), 400
    c = _try_open(idx)
    if not c:
        return jsonify({"ok": False, "error": f"cannot open index {idx}"}), 404
    with cap_lock:
        if cap:
            cap.release()
        cap = c
        current_index = idx
    return jsonify({"ok": True, "index": current_index})


@app.route("/health")
def health():
    ok = cap is not None and cap.isOpened()
    return jsonify({"ok": ok, "index": current_index})


if __name__ == "__main__":
    # Prime the camera once on start
    _open_first_available()
    app.run(host="0.0.0.0", port=PORT, debug=True)