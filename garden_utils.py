# garden_utils.py

def analyze_zone(zone_id):
    # Simulated logic — replace with real sensor data or image analysis
    zone_data = {
        "zone_1": {"moisture": 72, "status": "healthy"},
        "zone_2": {"moisture": 45, "status": "dry"},
        "zone_3": {"moisture": 88, "status": "overwatered"},
    }

    zone = zone_data.get(zone_id, None)
    if not zone:
        return {
            "zone_id": zone_id,
            "status": "unknown",
            "moisture_level": "N/A",
            "recommendation": "Zone not found"
        }

    recommendation = "No action needed"
    if zone["moisture"] < 50:
        recommendation = "Increase watering"
    elif zone["moisture"] > 85:
        recommendation = "Reduce watering"

    return {
        "zone_id": zone_id,
        "status": zone["status"],
        "moisture_level": f"{zone['moisture']}%",
        "recommendation": recommendation
    }

