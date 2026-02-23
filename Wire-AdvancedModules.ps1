# PowerShell
# Wire-AdvancedModules.ps1
# Backs up app.py, writes a feature-rich app.py with hydration/health/voice endpoints,
# ensures folders/files exist, and starts Flask.

$ErrorActionPreference = 'Stop'
cd C:\Users\alpha\Desktop\IngeniousIrrigation

# 0) Ensure structure
New-Item -ItemType Directory -Force -Path .\templates, .\static, .\static\audio, .\data | Out-Null

# 1) Backup current app.py
if (Test-Path .\app.py) {
  $bak = ".\app.py.bak_$(Get-Date -Format yyyyMMdd_HHmmss)"
  Copy-Item .\app.py $bak -Force
  Write-Host "Backed up app.py -> $bak" -ForegroundColor Yellow
}

# 2) Write new app.py (full content)
$appCode = @'
# app.py — Ingenious Irrigation: UI + Hydration/Health/Voice endpoints
from pathlib import Path
import json, io, base64
from flask import Flask, render_template, send_from_directory, request, jsonify

# --- Paths / storage ---
ROOT = Path(__file__).parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

SCHEDULE_JSON = DATA / "schedule.json"
DEFAULT_SCHEDULE = {"zones": {"1": {"minutes": 10, "enabled": True}}}

def load_schedule():
    if not SCHEDULE_JSON.exists():
        SCHEDULE_JSON.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2), encoding="utf-8")
    return json.loads(SCHEDULE_JSON.read_text(encoding="utf-8"))

def save_schedule(d):
    SCHEDULE_JSON.write_text(json.dumps(d, indent=2), encoding="utf-8")

# --- Optional modules (safe import) ---
def _safe_import(name, fallback):
    try:
        return __import__(name)
    except Exception:
        return fallback

# Hydration engine stub
class _HydrationStub:
    @staticmethod
    def score(signals: dict):
        # Simple heuristic if real model isn't available
        soil = float(signals.get("soil", 0.4))
        temp = float(signals.get("tempF", 85))
        rain = float(signals.get("rain_mm_24h", 0))
        # invert: 0 (very dry) .. 10 (oversaturated)
        val = 5.0
        if soil <= 0.25: val -= 2.5
        elif soil <= 0.35: val -= 1.0
        if temp >= 93: val -= 1.0
        if rain >= 8: val += 2.0
        return max(0.0, min(10.0, round(val, 2)))

# Health evaluator stub
class _HealthStub:
    @staticmethod
    def evaluate(payload: dict):
        # Return a dummy health vector; plug in your YOLO/green-index later
        return {"greenness": 0.72, "dry_patches": 0.12, "standing_water": False, "score": 0.78}

# Voice trainer stub
class _VoiceStub:
    @staticmethod
    def train(params: dict):
        return {"ok": True, "msg": "Voice training queued (stub)."}

    @staticmethod
    def say(text: str):
        # This is just a stub; use your TTS later
        return {"ok": True, "spoken": text}

hydration_engine = _safe_import("hydration_engine", _HydrationStub)
health_evaluator = _safe_import("health_evaluator", _HealthStub)
voice_trainer = _safe_import("voice_trainer", _VoiceStub)

# --- Flask app ---
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def _no_cache(resp):
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp

# --- UI routes ---
@app.get("/")
def dashboard():
    return render_template("dashboard.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/x-icon")

# --- Schedule API (keeps UI 'online') ---
@app.get("/api/schedule")
def api_get_schedule():
    return jsonify(load_schedule())

@app.post("/api/schedule/update")
def api_update_schedule():
    j = request.get_json(force=True, silent=True) or {}
    zone = str(j.get("zone", 1))
    minutes = max(0, int(j.get("minutes", 10)))
    data = load_schedule()
    data.setdefault("zones", {})
    data["zones"].setdefault(zone, {"minutes": 10, "enabled": True})
    data["zones"][zone]["minutes"] = minutes
    save_schedule(data)
    return jsonify({"ok": True, "zone": zone, "minutes": minutes})

# --- NEW: Hydration & Health & Voice endpoints ---
@app.post("/api/hydration/score")
def api_hydration_score():
    payload = request.get_json(force=True, silent=True) or {}
    # expects: {"signals": {...}}
    signals = payload.get("signals", {}) or {}
    try:
        score = hydration_engine.score(signals)  # real or stub
    except Exception as e:
        return jsonify({"ok": False, "error": f"hydration score failed: {e}"}), 500
    return jsonify({"ok": True, "hydration_score": score})

@app.post("/api/health/evaluate")
def api_health_eval():
    # accepts either {"signals": {...}} or {"image_b64": "..."} for future model use
    payload = request.get_json(force=True, silent=True) or {}
    try:
        result = health_evaluator.evaluate(payload)  # real or stub
    except Exception as e:
        return jsonify({"ok": False, "error": f"health evaluate failed: {e}"}), 500
    return jsonify({"ok": True, "result": result})

@app.post("/api/voice/train")
def api_voice_train():
    params = request.get_json(force=True, silent=True) or {}
    try:
        out = voice_trainer.train(params)  # real or stub
    except Exception as e:
        return jsonify({"ok": False, "error": f"voice train failed:
