import os, json, time, threading, datetime as dt
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

# Project paths
ROOT_DIR = os.getcwd()
DATA_DIR = os.path.join(ROOT_DIR, "data")
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")
LOG_FILE = os.path.join(LOGS_DIR, "watering.log")

# ---------------- Valve driver (GPIO on Pi, mock on Windows) ----------------
class ValveDriver:
    def __init__(self, pin: int = 27) -> None:
        self.pin = pin
        self._active = False
        try:
            try:
                import gpiozero  # type: ignore
                self._gpio = gpiozero.OutputDevice(pin, active_high=True, initial_value=False)
                self._is_mock = False
            except Exception:
                self._gpio = None
                self._is_mock = True
        except Exception:
            self._gpio = None
            self._is_mock = True

    def on(self) -> None:
        self._active = True
        if self._gpio:
            self._gpio.on()
        self._log("VALVE", f"ON (pin={self.pin}, mock={getattr(self, '_is_mock', True)})")

    def off(self) -> None:
        self._active = False
        if self._gpio:
            self._gpio.off()
        self._log("VALVE", f"OFF (pin={self.pin}, mock={getattr(self, '_is_mock', True)})")

    def _log(self, tag: str, msg: str) -> None:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} [{tag}] {msg}\n"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

# ---------------- Schedule data ----------------
@dataclass
class WaterJob:
    zone: str
    minutes: float
    start: Optional[str] = None  # ISO time string
    created_at: str = dt.datetime.now().isoformat(timespec="seconds")

def load_schedule() -> List[Dict[str, Any]]:
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def save_schedule(items: List[Dict[str, Any]]) -> None:
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception:
        pass

def _coerce_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

# ---------------- Public entry used by app.py ----------------
def handle_hydration_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts payload like:
      {"zone": "front", "action": "start", "minutes": 5}
      {"zone": "front", "action": "stop"}
      {"action":"schedule", "items":[{"zone":"front","minutes":10,"start":"06:00"}]}
    Returns a dict suitable for jsonify.
    """
    action = str(payload.get("action", "")).lower()
    zone = str(payload.get("zone", "main"))
    minutes = _coerce_float(payload.get("minutes", 0))

    # Lightweight single-valve control (extend as needed per zone->pin map)
    valve = ValveDriver(pin=27)

    if action in ("start", "run", "on"):
        valve.on()
        # Run in the background to turn off after N minutes (if minutes>0)
        if minutes > 0:
            def _auto_off(secs: float):
                time.sleep(secs)
                try:
                    valve.off()
                except Exception:
                    pass
            threading.Thread(target=_auto_off, args=(minutes*60,), daemon=True).start()
        return {"ok": True, "action": "start", "zone": zone, "minutes": minutes}

    if action in ("stop", "off", "cancel"):
        valve.off()
        return {"ok": True, "action": "stop", "zone": zone}

    if action == "schedule":
        items = payload.get("items") or []
        existing = load_schedule()
        # normalize and append
        for it in items:
            job = WaterJob(
                zone=str(it.get("zone", "main")),
                minutes=_coerce_float(it.get("minutes", 0)),
                start=it.get("start")
            )
            existing.append(asdict(job))
        save_schedule(existing)
        return {"ok": True, "action": "schedule", "count": len(items), "total": len(existing)}

    # Unknown action — just echo
    return {"ok": False, "error": f"unknown action '{action}'", "payload": payload}
# schedule_manager.py — JSON store for zone settings
import json
from pathlib import Path

DEFAULT = {"zones": {"1": {"minutes": 10, "enabled": True}}}

class ScheduleStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = DEFAULT.copy()
        self.load()

    def load(self):
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def set_zone(self, zone: int, cfg: dict):
        d = self.data.setdefault("zones", {})
        z = d.setdefault(str(zone), {})
        z.update(cfg)
