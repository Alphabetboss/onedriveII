"""
hydration_logic.py
Compute the Hydration Need Score (0..10; 0 = very dry, 10 = over-wet) from
AI detections, soil moisture %, and recent weather.

This produces a *score* only. Use ai/irrigation_rules.py to convert score -> minutes.
"""

from __future__ import annotations
from typing import Dict, List

def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def score_from_signals(
    detections: List[Dict],   # e.g. [{"name":"dead_grass","conf":0.72}, {"name":"water","conf":0.81}]
    soil_moisture_pct: float, # 0..100
    weather: Dict             # {"rain_mm_48h": float, "forecast_high_f": float}
) -> float:
    """
    Heuristic fusion:
     - Visual dryness (dead/brown) pulls score DOWN (drier).
     - Visual wetness (water/puddle/mud) pulls score UP (wetter).
     - Soil moisture pushes toward wet if high, dry if low.
     - Recent rainfall increases wetness.
     - Heat (>93F) nudges dryness.
    """
    base = 5.0  # neutral
    dry_bias  = 0.0
    wet_bias  = 0.0

    # Visual cues
    for det in detections or []:
        name = (det.get("name") or "").lower()
        conf = float(det.get("conf", 0.5))
        if name in {"dead_grass","brown","dry_patch"}:
            dry_bias  -= 2.0 * conf
        if name in {"water","puddle","mud","standing_water","leak"}:
            wet_bias  += 2.5 * conf
        if name in {"healthy_grass","green"}:
            wet_bias  += 0.2 * conf  # slightly toward wetter (green often correlates with adequate moisture)

    # Soil probe (linear map: 0% -> -3, 100% -> +3)
    soil = (soil_moisture_pct/100.0) * 6.0 - 3.0
    wet_bias += soil

    # Weather
    rain48 = float(weather.get("rain_mm_48h", 0.0) or 0.0)
    highF  = float(weather.get("forecast_high_f", 85.0) or 85.0)

    if rain48 >= 8.0:    # ~0.3 inch
        wet_bias += 2.0
    elif rain48 >= 3.0:  # drizzle/some rain
        wet_bias += 1.0

    if highF >= 93.0:
        dry_bias  -= 0.8

    score = base + dry_bias + wet_bias
    return float(_clip(score, 0.0, 10.0))
