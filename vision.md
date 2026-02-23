# Ingenious Irrigation — Vision & v1.0 Plan

## 1) Problem
Home irrigation wastes water due to fixed timers, poor feedback, and unnoticed leaks.

## 2) Solution (One-liner)
An AI-powered “sprinkler technician” that sees your yard, senses soil, checks weather, and adapts watering automatically.

## 3) Goals (v1.0)
- Safe, reliable watering for a single home yard (1–4 zones).
- Automatic schedule adjustments via **Hydration Need Score (0–10)**.
- Weather-aware overrides for Houston, TX conditions.
- Leak/puddle detection from camera; skip/stop on anomalies.
- Clean dashboard with avatar guide (“Asta”) and clear logs.

## 4) Architecture
- **Edge Controller**: Raspberry Pi (3B+ or 5), 5V relay for valves, camera, moisture sensor, DHT temp/humidity.
- **Software**: Python 3.10+, Flask (web/API), YOLOv8 (hydration detection), schedule manager, weather client, logging.
- **UI**: Flask templates + static assets, Asta avatar GLB in browser.
- **Data**: `schedule.json`, `watering.log`, `hydration_analysis.log`, cached weather.

## 5) Hardware (v1.0 tested)
- RPi 3B+/5, 5V relay module, camera module (RPi camera or USB), soil moisture probe, DHT11/22.
- Optional: Drone camera (future).

## 6) AI & Hydration Score
- **YOLOv8** model → detects: grass health, dead_grass, water/puddle/mud, etc.
- **Hydration Need Score** (inverted):
  - 0 = very dry → needs longer watering
  - 5 = optimal → normal watering
  - 10 = oversaturated → skip watering

### Score → Time Mapping (baseline: 10 min @ 5:00 AM on watering days)
| Score | Adjustment | Example Duration |
|------:|-----------:|-----------------:|
| 0–1   | +80–60%    | 18–16 min        |
| 2–3   | +40–20%    | 14–12 min        |
| 4–6   | +0%        | 10 min           |
| 7–8   | −30–50%    | 7–5 min          |
| 9–10  | Skip       | 0 min            |

> Final duration also considers: soil moisture %, 48h rainfall, today’s forecast high/ET proxy.

## 7) Weather/Location Policy (Houston, TX)
- Target **1–1.5 in/week**, deep & infrequent.
- **>93°F highs** → allow more frequent watering (split cycles to avoid runoff).
- **Rain in last 24–48h** → cut or skip.
- Always water **early morning** (default 5:00 AM).

## 8) Scheduling
- Homeowner sets baseline (daily / every X days / per-zone).
- **AI override** runs nightly before watering window:
  1. Gather: latest camera frame(s), moisture, weather.
  2. Compute Hydration Score.
  3. Decide: extend/normal/reduce/skip.
  4. Log plan & reasons; expose on dashboard.

## 9) Safety & Emergencies
- **Leak/puddle spike** → stop zone, alert user, lockout until manual clear.
- **Camera offline / sensor error** → fall back to conservative baseline; log warning.
- **Relay watchdog** and max-on-time per zone.

## 10) Data & Privacy
- All inference runs locally on the Pi by default.
- Logs stored locally; optional cloud export later.

## 11) KPIs (What “done” looks like)
- ≥20% water savings vs. fixed schedule over 30 days.
- Zero unbounded run events (max-on-time works).
- <2 false leak alerts per 30 days.
- Dashboard shows: last/next watering per zone, reason codes, and health trend.

## 12) Roadmap
- v1.0: Single-yard, up to 4 zones, local-only, Asta avatar, YOLO hydration + moisture + weather fusion.
- v1.1: Multi-zone UI, voice commands, better anomaly explanations.
- v1.2: Drone scan (optional), multi-home support, cloud backup.
- v1.3: Installer wizard, OTA updates, user profiles.

## 13) Repo Pointers (expected files)
- `app.py` (Flask web/API)
- `schedule_manager.py` (start/stop/get schedule, AI override)
- `scripts/camera_util.py` (frame capture)
- `ai/hydration_logic.py` (score + duration)
- `services/weather_client.py` (weather)
- `storage/schedule_store.py` + `schedule.json`
- `static/models/astra.glb`, `templates/*.html`, `static/style.css`
- `logs/` (`watering.log`, `hydration_analysis.log`)
