"""
irrigation_rules.py
Combine AI hydration score, soil moisture, and weather into a watering decision.

Key inputs:
- hydration_score: 0(dry) .. 10(wet)  (inverted scale from your spec)
- soil_moisture_pct: 0..100 from MoistureSensor
- weather: dict with fields:
    {"rain_mm_48h": float, "forecast_high_f": float, "raining_now": bool}
- flags: dict of booleans like {"leak_detected": False, "puddle_detected": False}
- baseline_minutes: homeowner baseline (e.g., 10)

Output: dict { "minutes": int, "skip": bool, "reasons": [codes], "lockout": bool }
"""

from __future__ import annotations
from typing import List, Dict

def map_score_to_multiplier(score: float) -> float:
    # From your vision doc: baseline 10 min @ score 4..6
    if score <= 1: return 1.8
    if score <= 3: return 1.2 + (3 - score) * 0.1  # 2->1.3, 3->1.2
    if score <= 6: return 1.0
    if score <= 8: return 0.5 + (8 - score) * 0.1  # 7->0.6, 8->0.5
    return 0.0  # 9..10 -> skip

def decide_watering(
    hydration_score: float,
    soil_moisture_pct: float,
    weather: Dict,
    flags: Dict | None = None,
    baseline_minutes: int = 10,
) -> Dict:
    flags = flags or {}
    reasons: List[str] = []

    # Safety: leaks/puddles
    if flags.get("leak_detected") or flags.get("puddle_detected"):
        return {"minutes": 0, "skip": True, "reasons": ["WET_AI", "SAFETY_LOCK"], "lockout": True}

    # Weather skips
    rain_mm_48h = float(weather.get("rain_mm_48h", 0.0) or 0.0)
    forecast_high_f = float(weather.get("forecast_high_f", 85.0) or 85.0)
    raining_now = bool(weather.get("raining_now", False))

    if raining_now or rain_mm_48h >= 8.0:  # ~0.3 in
        reasons += ["RAIN_SKIP"]
        return {"minutes": 0, "skip": True, "reasons": reasons, "lockout": False}

    # Score multiplier
    mult = map_score_to_multiplier(hydration_score)
    if mult == 0.0:
        reasons += ["WET_AI"]
        return {"minutes": 0, "skip": True, "reasons": reasons, "lockout": False}

    # Soil moisture biases (±10%)
    if soil_moisture_pct < 25:
        mult *= 1.1; reasons += ["MOISTURE_LOW"]
    elif soil_moisture_pct > 70:
        mult *= 0.9; reasons += ["MOISTURE_HIGH"]

    # Heat boost if >93F
    if forecast_high_f >= 93.0:
        mult *= 1.2
        reasons += ["HEAT_BOOST"]

    minutes = int(round(baseline_minutes * mult))
    minutes = max(0, min(30, minutes))  # clamp

    # Label general AI reason
    if hydration_score <= 3: reasons.insert(0, "DRY_AI")
    elif hydration_score >= 7: reasons.insert(0, "WET_AI")
    else: reasons.insert(0, "OPTIMAL_AI")

    skip = minutes == 0
    return {"minutes": minutes, "skip": skip, "reasons": reasons, "lockout": False}
