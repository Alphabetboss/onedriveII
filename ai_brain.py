# ai_brain.py — converts signals to watering minutes.
# Signals expected shape:
#   {"soil": 0.0..1.0, "tempF": 75, "rain_mm_24h": 0, "ai_flags":{"standing_water":False,"very_dry":False}}
def decide_minutes_from_signals(base_minutes: int, s: dict) -> int:
    soil = float(s.get("soil", 0.4))        # lower is drier
    temp = float(s.get("tempF", 85))
    rain = float(s.get("rain_mm_24h", 0))
    flags = s.get("ai_flags", {}) or {}

    # Reduce or skip if recent rain / standing water
    if flags.get("standing_water") or rain >= 8:   # ~8 mm ≈ 0.3 in
        return 0

    minutes = base_minutes

    # Hot boost
    if temp >= 93: minutes += 6
    elif temp >= 88: minutes += 3

    # Soil dryness boost/cut
    if soil <= 0.25: minutes += 6
    elif soil <= 0.35: minutes += 3
    elif soil >= 0.70: minutes -= 5

    # Gentle cut if any rain
    if 2 <= rain < 8:
        minutes = max(0, minutes - 5)

    # Clamp sane bounds
    return max(0, min(int(minutes), 45))
