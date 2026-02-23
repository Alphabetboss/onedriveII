# PowerShell
# check_ii_scripts.ps1 — verifies core files and creates missing ones with safe stubs
# Run from project root:  .\check_ii_scripts.ps1

$ErrorActionPreference = "Stop"

function Ensure-Folder($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

$ROOT      = (Get-Location).Path
$TPL       = Join-Path $ROOT "templates"
$STATIC    = Join-Path $ROOT "static"
$DATA      = Join-Path $ROOT "data"
$MODELS    = Join-Path $ROOT "models"
$CAMERA    = Join-Path $ROOT "camera"

$folders = @($TPL,$STATIC,$DATA,$MODELS,$CAMERA)
$folders | ForEach-Object { Ensure-Folder $_ }

# ---------- File templates (only created if missing) ----------
# Small helper to write a file if it doesn't exist
function Ensure-File($path, [string]$content) {
  if (!(Test-Path $path)) {
    $dir = Split-Path $path -Parent
    Ensure-Folder $dir
    Set-Content -Path $path -Value $content -Encoding UTF8
    Write-Host "Created $($path.Replace($ROOT,'').TrimStart('\'))" -ForegroundColor Yellow
  } else {
    Write-Host "OK     $($path.Replace($ROOT,'').TrimStart('\'))" -ForegroundColor DarkGray
  }
}

# -------- Default data files ----------
$SCHEDULE_JSON = @"
{
  "zones": { "1": { "minutes": 10, "enabled": true }},
  "last_updated": "$(Get-Date -Format o)"
}
"@
Ensure-File (Join-Path $DATA "schedule.json") $SCHEDULE_JSON

$WEATHER_CACHE = @"
{
  "source": "stub",
  "temp_f": 78.0,
  "humidity": 0.55,
  "rain_in_last_24h": 0.00,
  "updated": "$(Get-Date -Format o)"
}
"@
Ensure-File (Join-Path $DATA "weather_cache.json") $WEATHER_CACHE

# -------- Minimal dashboard (so / route renders) ----------
$DASHBOARD_HTML = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Ingenious Irrigation</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;background:#0a0d10;color:#d9ffd9}
    header{padding:16px 20px;background:#0f141a;border-bottom:1px solid #203029}
    .chip{display:inline-block;margin-right:8px;padding:6px 10px;border:1px solid #335;border-radius:12px}
    .card{background:#111822;border:1px solid #23313a;border-radius:14px;padding:16px;margin:16px}
    button{background:#1a2b22;border:1px solid #2e6d46;color:#9cff9c;border-radius:10px;padding:10px 16px;cursor:pointer}
    button:hover{filter:brightness(1.1)}
    input{background:#0c1217;border:1px solid #203029;color:#d9ffd9;padding:8px;border-radius:10px}
  </style>
</head>
<body>
  <header>
    <h2>Ingenious Irrigation — Dashboard</h2>
    <span class="chip">Status: <strong id="status">online</strong></span>
  </header>
  <main class="card">
    <div>
      <label>Start Time: <input id="start" type="time" value="05:00"/></label>
      <label style="margin-left:12px;">Duration (min): <input id="dur" type="number" value="10" min="1"/></label>
      <button id="save">Save</button>
    </div>
    <pre id="summary" style="margin-top:12px;"></pre>
  </main>
  <script>
    async function save(){
      const body = { zones: { "1": { minutes: Number(document.querySelector('#dur').value)||10, enabled: true } } };
      const res = await fetch('/api/schedule', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      document.querySelector('#summary').textContent = JSON.stringify(await res.json(), null, 2);
    }
    document.querySelector('#save').addEventListener('click', save);
    fetch('/api/schedule').then(r=>r.json()).then(d=>{
      document.querySelector('#summary').textContent = JSON.stringify(d,null,2);
    });
  </script>
</body>
</html>
"@
Ensure-File (Join-Path $TPL "dashboard.html") $DASHBOARD_HTML

# -------- Python stubs for modules your app often imports ----------
$HYDRATION_ENGINE = @"
# hydration_engine.py — safe stub that computes a 0–10 hydration_need score
# 0 = very dry (needs more water), 5 = good/normal, 10 = oversaturated (skip)
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

def compute_hydration(image_path: str | None = None,
                      sensors: Dict[str, Any] | None = None,
                      weather: Dict[str, Any] | None = None) -> Dict[str, Any]:
    sensors = sensors or {}
    weather = weather or {}
    soil = float(sensors.get('soil_moisture', 0.35))   # 0–1
    rain = float(weather.get('rain_in_last_24h', 0.0)) # inches
    temp = float(weather.get('temp_f', 82.0))          # F

    # Normalize: more moisture and rain push toward oversaturated (higher score)
    oversat = min(1.0, max(0.0, soil*0.7 + (rain/1.5)*0.3))
    heat_bias = 0.0
    if temp >= 93: heat_bias = -1.0     # hotter -> more need -> lower score
    elif temp <= 45: heat_bias = +0.5   # cold -> less need

    score = 10.0*oversat + heat_bias
    score = max(0.0, min(10.0, score))

    return {
        "hydration_need": round(score, 2),
        "explain": {
            "soil_moisture": soil,
            "rain_24h_in": rain,
            "temp_f": temp,
            "heat_bias": heat_bias
        }
    }
"@
Ensure-File (Join-Path $ROOT "hydration_engine.py") $HYDRATION_ENGINE

$HEALTH_EVALUATOR = @"
# health_evaluator.py — safe stub; returns simple health signals for the lawn
from __future__ import annotations
from typing import Dict, Any

def assess(image_path: str | None = None) -> Dict[str, Any]:
    # Stubbed heuristics; integrate YOLO later
    return {
        "green_coverage": 0.72,   # 0–1
        "dead_patches": 0.05,     # 0–1
        "standing_water": False,
        "notes": "Stub evaluator; replace with YOLO predictions."
    }
"@
Ensure-File (Join-Path $ROOT "health_evaluator.py") $HEALTH_EVALUATOR

$WEATHER_CLIENT = @"
# weather_client.py — local cache fallback (no API key required)
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DATA = Path(__file__).parent / 'data'
CACHE = DATA / 'weather_cache.json'

def get_weather() -> Dict[str, Any]:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return { 'source':'stub', 'temp_f':78.0, 'humidity':0.55, 'rain_in_last_24h':0.0 }
"@
Ensure-File (Join-Path $ROOT "weather_client.py") $WEATHER_CLIENT

$CAMERA_UTIL = @"
# camera_util.py — returns a latest image path if present
from __future__ import annotations
from pathlib import Path
from typing import Optional

CAMERA_DIR = Path(__file__).parent / 'camera'

def latest_image() -> Optional[str]:
    if not CAMERA_DIR.exists(): return None
    imgs = sorted([p for p in CAMERA_DIR.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png'}], reverse=True)
    return str(imgs[0]) if imgs else None
"@
Ensure-File (Join-Path $ROOT "camera_util.py") $CAMERA_UTIL

$VOICE_TRAINER = @"
# voice_trainer.py — placeholder; no external deps required
def train_wake_word(data_dir: str = 'data/voice'):
    return {'status':'ok','samples':0,'note':'stub only'}

def tts(text: str, outfile: str | None = None):
    # No audio libs by default — just echo for now
    return {'status':'ok','message':text}
"@
Ensure-File (Join-Path $ROOT "voice_trainer.py") $VOICE_TRAINER

$RELAY_CONTROLLER = @"
# relay_controller.py — safe, GPIO-optional
from __future__ import annotations
import os, time

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False

RELAY_PIN = int(os.getenv('II_RELAY_PIN','17'))

def setup():
    if _HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
    return _HAS_GPIO

def water_for(seconds: float = 10.0):
    if _HAS_GPIO:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(max(0.0, seconds))
        GPIO.output(RELAY_PIN, GPIO.LOW)
        return {'status':'ok','pin':RELAY_PIN,'seconds':seconds,'gpio':True}
    else:
        # Simulate for dev machines
        time.sleep(min(0.1, seconds))
        return {'status':'simulated','pin':RELAY_PIN,'seconds':seconds,'gpio':False}
"@
Ensure-File (Join-Path $ROOT "relay_controller.py") $RELAY_CONTROLLER

$SCHEDULE_MANAGER = @"
# schedule_manager.py — tiny reader/writer around data/schedule.json
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DATA = Path(__file__).parent / 'data'
DATA.mkdir(exist_ok=True)
SCHEDULE_JSON = DATA / 'schedule.json'
DEFAULT = {'zones': {'1': {'minutes': 10, 'enabled': True}}}

def load() -> Dict[str, Any]:
    if not SCHEDULE_JSON.exists():
        SCHEDULE_JSON.write_text(json.dumps(DEFAULT, indent=2), encoding='utf-8')
    return json.loads(SCHEDULE_JSON.read_text(encoding='utf-8'))

def save(d: Dict[str, Any]) -> Dict[str, Any]:
    SCHEDULE_JSON.write_text(json.dumps(d, indent=2), encoding='utf-8')
    return d
"@
Ensure-File (Join-Path $ROOT "schedule_manager.py") $SCHEDULE_MANAGER

# -------- Minimal Flask app (only if app.py is missing) ----------
$APP_PY = @"
# app.py — minimal, stable server using the stubs above
from pathlib import Path
from flask import Flask, jsonify, render_template, request
import schedule_manager as sm
import weather_client as wc
import hydration_engine as he
import health_evaluator as hv
import camera_util as cu

ROOT = Path(__file__).parent
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.get('/')
def home():
    return render_template('dashboard.html')

@app.get('/api/schedule')
def api_get_schedule():
    return jsonify(sm.load())

@app.post('/api/schedule')
def api_set_schedule():
    body = request.get_json(force=True, silent=True) or {}
    if 'zones' not in body: 
        d = sm.load()
    else:
        d = sm.save({'zones': body.get('zones')})
    return jsonify({'ok': True, 'schedule': d})

@app.get('/api/status')
def api_status():
    w = wc.get_weather()
    img = cu.latest_image()
    health = hv.assess(img)
    hyd = he.compute_hydration(image_path=img, sensors={'soil_moisture':0.35}, weather=w)
    return jsonify({'online': True, 'weather': w, 'health': health, 'hydration': hyd})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
"@
Ensure-File (Join-Path $ROOT "app.py") $APP_PY

# -------- Requirements (text, not enforced) ----------
$REQ = @"
flask
# optional on Pi:
# RPi.GPIO
"@
Ensure-File (Join-Path $ROOT "requirements.txt") $REQ

Write-Host ""
Write-Host "Check complete." -ForegroundColor Cyan
