# app.py — Astra + Garden dashboard
import os, logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, Response, render_template
import numpy as np, cv2
import ii_config as config
from scripts.camera_util import get_frame_bgr
from flask import render_template
from flask import request, jsonify
import threading
from flask import request, jsonify
import csv, os, time

APP_HOST = getattr(config, "APP_HOST", "127.0.0.1")
APP_PORT = getattr(config, "APP_PORT", 5051)
DEBUG    = getattr(config, "DEBUG", True)
LOG_DIR  = getattr(config, "LOG_DIR", os.path.join(os.getcwd(), "logs"))
LOG_FILE = getattr(config, "LOG_FILE", os.path.join(LOG_DIR, "app.log"))

# Optional schedule manager stubs
try:
    from schedule_manager import start_watering, stop_watering, get_status
except Exception:
    def start_watering(*a, **k): return {"ok": True}
    def stop_watering(*a, **k): return {"ok": True}
    def get_status(): return {"active": False, "zone": 1, "remaining_sec": 0}

app = Flask(__name__, static_folder="static", template_folder="templates")

# Logging
os.makedirs(LOG_DIR, exist_ok=True)
handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
app.logger.addHandler(handler)

# --- Simple AI state for Astra (expand later) ---
_ai_state = {"state":"idle", "line":"Ready to tend the garden."}

@app.get("/")
def root():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "IngeniousIrrigation", "host": APP_HOST, "port": APP_PORT})

def _green_ratio(frame_bgr):
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 40, 40], dtype=np.uint8)
    upper = np.array([85, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return float(np.count_nonzero(mask)) / mask.size, mask

@app.get("/capture.jpg")
def capture_jpg():
    frame = get_frame_bgr()
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return jsonify({"ok": False, "error": "imencode failed"}), 500
    return Response(buf.tobytes(), mimetype="image/jpeg")
# app.py (additions)
from flask import render_template, request, jsonify
# near other imports at top of app.py
import threading

# Paste this after /probe and before the app.run block
@app.route("/api/hydration", methods=["POST"])
def api_hydration_impl():
    """
    Receives JSON payloads from the YOLO integrator and delegates to
    schedule_manager.handle_hydration_message(...) in a background thread.
    Returns quickly to the caller (202).
    """
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        app.logger.exception("api_hydration: invalid JSON")
        return jsonify({"ok": False, "error": "invalid json", "detail": str(e)}), 400

    try:
        from schedule_manager import handle_hydration_message
    except Exception as e:
        app.logger.exception("api_hydration: handler import failed")
        return jsonify({"ok": False, "error": "handler unavailable", "detail": str(e)}), 500

    # run handler in background thread so HTTP returns fast
    try:
        threading.Thread(target=handle_hydration_message, args=(payload, 1, 10), daemon=True).start()
    except Exception as e:
        app.logger.exception("api_hydration: failed to spawn thread")
        return jsonify({"ok": False, "error": "thread_failed", "detail": str(e)}), 500

    # optional: notify dashboards via socketio if you have socketio in app
    s = globals().get("socketio")
    if s:
        try:
            s.emit("hydration_update", payload)
        except Exception:
            app.logger.exception("api_hydration: socketio emit failed")

    return jsonify({"ok": True}), 202

@app.route("/avatar")
def avatar_closeup():
    # Renders the face-closeup page. Ensure templates/avatar_closeup.html exists,
    # and static/models/astra.glb is present.
    return render_template("avatar_closeup.html")
HYDRATION_CSV = getattr(config, "HYDRATION_CSV", "hydration_scores.csv")
HYDRATION_THRESHOLD = getattr(config, "HYDRATION_THRESHOLD", 6.5)  # example

def api_hydration_impl():
    """
    Accept JSON posted by external adapter or other company code.
    Expected JSON (example):
    {
      "timestamp":"2025-09-06T00:00:00Z",
      "green_coverage":0.32,
      "dead_grass_pct":0.0,
      "standing_water": false,
      "puddles_conf": 0.0,
      "detections": [ { "class":"dry", "conf":0.8, "bbox":[x,y,w,h] }, ... ],
      "hydration_need": 7.2  # optional, we can compute if not present
    }
    """
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "error": "no JSON body"}), 400

        # compute a hydration metric if caller didn't provide one
        hydration_need = data.get("hydration_need")
        if hydration_need is None:
            # simple placeholder heuristic — tune to your model
            green = float(data.get("green_coverage", 0.0))
            hydration_need = round(min(10.0, max(0.0, (1.0 - green) * 10.0)), 2)

        # write to CSV (append)
        header_needed = not os.path.exists(HYDRATION_CSV)
        row = {
            "timestamp": data.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
            "hydration_need": hydration_need,
            "green_coverage": data.get("green_coverage", ""),
            "dead_grass_pct": data.get("dead_grass_pct", ""),
            "standing_water": data.get("standing_water", False)
        }
        with open(HYDRATION_CSV, "a", newline="", encoding="utf8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if header_needed:
                writer.writeheader()
            writer.writerow(row)

        # optional: if hydration need high, trigger watering via schedule_manager
        try:
            if hydration_need >= HYDRATION_THRESHOLD:
                # start_watering(zone, seconds) - adjust args to your schedule_manager signature
                start_watering(zone=1, duration_sec=60)
        except Exception as e:
            # don't fail the whole endpoint if schedule_manager has an error
            app.logger.warning("schedule_manager start_watering errored: %s", e)

        return jsonify({"ok": True, "hydration_need": hydration_need})
    except Exception as e:
        app.logger.exception("api_hydration error")
        return jsonify({"ok": False, "error": str(e)}), 500
@app.post("/chat")
def chat_api():
    data = request.get_json(force=True) or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"reply": "I didn't hear anything. Try again?"})
    try:
        # If you already have an LLM client, use it here:
        from llm_client import local_chat
        reply = local_chat(user_text)
    except Exception:
        # Safe fallback so you can test right now
        reply = f"You said: {user_text}. I’m Asta!"
    return jsonify({"reply": reply})

@app.get("/capture_overlay.jpg")
def capture_overlay_jpg():
    frame = get_frame_bgr()
    ratio, mask = _green_ratio(frame)  # mask is 0..255, shape HxW
    # tint green where mask>0
    green = np.zeros_like(frame); green[:,:,1] = 255
    alpha = 0.35
    m = (mask.astype(np.float32)/255.0)[:, :, None]
    blended = (frame*(1.0 - alpha*m) + green*(alpha*m)).clip(0,255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", blended, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return jsonify({"ok": False, "error": "imencode failed"}), 500
    return Response(buf.tobytes(), mimetype="image/jpeg")
# app.py (additions)
from flask import render_template, request, jsonify

@app.get("/probe")
def probe():
    try:
        frame = get_frame_bgr()
        ratio, _ = _green_ratio(frame)
        hydration_need = round(min(10.0, max(0.0, ratio * 10.0)), 2)  # placeholder mapping
        return jsonify({"ok": True, "hydration_need": hydration_need, "green_ratio": round(ratio, 4), "status": get_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/ai/state")
def api_ai_state():
    return jsonify(_ai_state)

if __name__ == "__main__":
    print(f"Running at http://{APP_HOST}:{APP_PORT}")
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)
# add near other imports at top
from flask import request, jsonify
# if handler is in another file, import it
# from schedule_manager import handle_hydration_message

# HTTP endpoint to receive hydration payloads from the YOLO process
@app.route("/api/hydration", methods=["POST"])
def api_hydration_impl():
    """
    Receives JSON payloads from YOLO integrator:
    {
      "timestamp": "...",
      "green_coverage": 0.12,
      "dead_grass_pct": 0.0,
      "standing_water": false,
      "puddles_conf": 0.0,
      "detections": [...]
    }
    This endpoint calls handle_hydration_message(payload) to take action.
    """
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        return jsonify({"ok": False, "error": "invalid json", "detail": str(e)}), 400

    # Non-blocking: delegate to a thread so request returns fast
    try:
        import threading
        # IMPORT: adjust import path if schedule_manager.py sits in a package
        from schedule_manager import handle_hydration_message
        threading.Thread(target=handle_hydration_message, args=(payload, 1, 10)).start()
        # If you also use socketio, emit the payload to connected dashboards
        s = globals().get("socketio")
        if s:
            try:
                s.emit("hydration_update", payload)   # only if socketio available
            except Exception:
                app.logger.exception("api_hydration: socketio emit failed")
        return jsonify({"ok": True}), 202
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



# --- Guarded registration added by patch to avoid duplicate endpoint registration ---
if "api_hydration" not in app.view_functions:
    app.add_url_rule("/api/hydration", endpoint="api_hydration", view_func=api_hydration_impl, methods=["POST"])
else:
    app.logger.info("api_hydration endpoint already registered; skipping duplicate registration.")
# --- end patch ---