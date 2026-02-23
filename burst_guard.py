# burst_guard.py — detects abnormal flow or standing water and triggers shutdown
import time

class BurstGuard:
    def __init__(self, hw, notifier, flow_sensor=None):
        self.hw = hw
        self.notifier = notifier
        self.flow_sensor = flow_sensor   # optional: object with .gpm() or .ticks_per_sec()

        # heuristics
        self.max_continuous_minutes = 90
        self.last_on_ts = None
        self.last_seen_standing = False

    def _standing_water_detected(self) -> bool:
        # Placeholder for your AI detector (e.g., YOLO flag shared via file or IPC)
        # You can replace with real signal; here we check a temp file flag if present.
        try:
            with open("data/standing_water.flag","r") as f:
                v = f.read().strip().lower()
                return v in ("1","true","yes")
        except Exception:
            return False

    def _flow_abnormal(self) -> bool:
        if not self.flow_sensor: return False
        try:
            gpm = float(self.flow_sensor.gpm())
            return gpm > 20.0  # adjust to your plumbing
        except Exception:
            return False

    def check(self):
        # standing water AI signal
        standing = self._standing_water_detected()
        if standing and not self.last_seen_standing:
            self.last_seen_standing = True
            return True, "Standing water detected by AI."
        self.last_seen_standing = standing

        # abnormal flow
        if self._flow_abnormal():
            return True, "Abnormally high flow rate."

        # overly long watering (safety cutoff)
        if self.last_on_ts and (time.time() - self.last_on_ts) > self.max_continuous_minutes*60:
            return True, "Exceeded maximum continuous watering time."

        return False, ""
