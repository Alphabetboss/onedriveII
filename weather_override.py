# weather_override.py
"""
Weather-based override logic for Ingenious Irrigation.

This module DOES NOT call any external weather API by itself. Instead it provides:
- `WeatherSnapshot` data structure (simple dict expected format)
- `decide_override(snapshot, config)` which returns an override decision dict
- Reasoning rules and thresholds that are customizable via config

Expected snapshot keys (example):
{
    "temp_c": 30.0,
    "temp_f": 86.0,
    "humidity": 50,             # relative humidity %
    "precip_mm_24h": 0.0,       # rainfall in mm last 24 hours
    "precip_today_mm": 0.0,
    "pop": 20,                  # probability of precipitation next window (0-100)
    "wind_kph": 5.0,
    "soil_moisture_pct": None,  # optional sensor reading 0-100
    "timestamp": "2025-11-13T05:00:00Z"
}

Return value example:
{
    "action": "skip" | "reduce" | "normal" | "increase",
    "duration_factor": 0.0 to 2.0,
    "reason": "human-readable reason",
    "details": {...}
}

Defaults are tuned for a Texas-style schedule (deep & infrequent) but are configurable.
"""

from typing import Dict, Any
from datetime import datetime, timedelta


# sensible default config — tweak to taste
DEFAULT_CONFIG = {
    "min_precip_skip_mm": 6.0,       # if > mm in past 24h skip
    "recent_rain_window_hours": 24,
    "pop_skip_threshold": 60,        # percent; if high chance of rain soon -> skip
    "soil_moisture_high_pct": 70,    # if soil moisture sensor >= this -> skip
    "soil_moisture_low_pct": 25,     # if soil moisture low -> maybe increase
    "hot_temp_f": 93.0,              # temps above -> consider increasing
    "very_hot_temp_f": 100.0,        # strong increase
    "wind_cutoff_kph": 30.0,         # high wind reduces efficiency -> reduce duration
    "max_increase_factor": 1.5,
    "max_reduce_factor": 0.5,
    "base_weekly_inches": 1.25,      # target weekly inches (for context)
    # Minimal precipitation considered (mm -> inches ~ mm/25.4)
    "mm_per_inch": 25.4,
}


def decide_override(snapshot: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Decide whether to skip/reduce/normal/increase watering given a weather snapshot.

    Important: this is deterministic and designed for embedding into your schedule manager.
    snapshot: weather and optional soil data (see top docstring)
    config: override default thresholds
    """
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)

    # normalize input
    precip_24 = snapshot.get("precip_mm_24h") or snapshot.get("precip_today_mm") or 0.0
    pop = snapshot.get("pop", 0)  # probability of precipitation %
    soil_pct = snapshot.get("soil_moisture_pct")
    temp_f = snapshot.get("temp_f")
    wind = snapshot.get("wind_kph", 0.0)

    decision = {
        "action": "normal",
        "duration_factor": 1.0,
        "reason": "Default — no override applied",
        "details": {
            "precip_24_mm": precip_24,
            "pop": pop,
            "soil_moisture_pct": soil_pct,
            "temp_f": temp_f,
            "wind_kph": wind
        }
    }

    # 1) Skip if there was significant rain recently
    if precip_24 >= cfg["min_precip_skip_mm"]:
        decision.update({
            "action": "skip",
            "duration_factor": 0.0,
            "reason": f"Recent rainfall {precip_24:.1f} mm >= {cfg['min_precip_skip_mm']} mm — skipping watering."
        })
        return decision

    # 2) Skip if soil moisture sensor indicates already wet
    if soil_pct is not None:
        try:
            soil_pct = float(soil_pct)
            if soil_pct >= cfg["soil_moisture_high_pct"]:
                decision.update({
                    "action": "skip",
                    "duration_factor": 0.0,
                    "reason": f"Soil moisture {soil_pct:.0f}% >= {cfg['soil_moisture_high_pct']}% — skipping watering."
                })
                return decision
        except Exception:
            pass

    # 3) Skip if high probability of rain in next window
    if pop >= cfg["pop_skip_threshold"]:
        decision.update({
            "action": "skip",
            "duration_factor": 0.0,
            "reason": f"Chance of precipitation {pop}% >= {cfg['pop_skip_threshold']}% — skipping scheduled run."
        })
        return decision

    # 4) Reduce if wind is too high (to avoid evaporative loss and uneven coverage)
    if wind >= cfg["wind_cutoff_kph"]:
        decision.update({
            "action": "reduce",
            "duration_factor": max(cfg["max_reduce_factor"], 0.3),
            "reason": f"High wind {wind} kph >= {cfg['wind_cutoff_kph']} kph — reducing duration to limit waste."
        })
        return decision

    # 5) Temperature-driven adjustments (hot weather -> increase)
    if temp_f is not None:
        if temp_f >= cfg["very_hot_temp_f"]:
            decision.update({
                "action": "increase",
                "duration_factor": cfg["max_increase_factor"],
                "reason": f"Very hot {temp_f}°F >= {cfg['very_hot_temp_f']}°F — increasing duration."
            })
            return decision
        if temp_f >= cfg["hot_temp_f"]:
            # small bump for hot but not extreme
            decision.update({
                "action": "increase",
                "duration_factor": min(1.25, cfg["max_increase_factor"]),
                "reason": f"Hot {temp_f}°F >= {cfg['hot_temp_f']}°F — moderate increase to avoid heat stress."
            })
            return decision

    # 6) If soil is very dry, consider slight increase
    if soil_pct is not None:
        try:
            soil_pct = float(soil_pct)
            if soil_pct <= cfg["soil_moisture_low_pct"]:
                factor = min(1.25, cfg["max_increase_factor"])
                decision.update({
                    "action": "increase",
                    "duration_factor": factor,
                    "reason": f"Soil moisture low ({soil_pct:.0f}%) <= {cfg['soil_moisture_low_pct']}% — increasing duration."
                })
                return decision
        except Exception:
            pass

    # 7) If light precipitation occurred but not enough to skip, reduce
    if 0 < precip_24 < cfg["min_precip_skip_mm"]:
        small_reduce = max(0.6, 1.0 - (precip_24 / (cfg["min_precip_skip_mm"] * 2)))
        decision.update({
            "action": "reduce",
            "duration_factor": small_reduce,
            "reason": f"Light recent precipitation ({precip_24:.1f} mm) — reducing duration proportionally."
        })
        return decision

    # default: normal
    decision.update({"action": "normal", "duration_factor": 1.0, "reason": "Conditions normal."})
    return decision


# Example small helper to apply decision to a planned duration
def apply_decision_to_duration(planned_minutes: float, decision: Dict[str, Any]) -> float:
    """
    Returns the new duration in minutes after applying decision.duration_factor.
    """
    factor = float(decision.get("duration_factor", 1.0))
    if decision.get("action") == "skip":
        return 0.0
    new_dur = planned_minutes * factor
    return round(new_dur, 2)


# quick demo / test
if __name__ == "__main__":
    # sample snapshots
    snapshots = [
        {"temp_f": 95.0, "precip_mm_24h": 0.0, "pop": 5, "soil_moisture_pct": 30, "wind_kph": 5},
        {"temp_f": 78.0, "precip_mm_24h": 10.0, "pop": 10, "soil_moisture_pct": 60, "wind_kph": 8},
        {"temp_f": 82.0, "precip_mm_24h": 1.0, "pop": 20, "soil_moisture_pct": 55, "wind_kph": 35},
        {"temp_f": 101.0, "precip_mm_24h": 0.0, "pop": 0, "soil_moisture_pct": 20, "wind_kph": 3},
    ]
    plan = 10.0  # planned minutes

    for snap in snapshots:
        dec = decide_override(snap)
        applied = apply_decision_to_duration(plan, dec)
        print(f"Snapshot: {snap}")
        print(f"Decision: {dec['action']} ({dec['duration_factor']}) reason: {dec['reason']}")
        print(f"Planned {plan} min -> Applied {applied} min\n")