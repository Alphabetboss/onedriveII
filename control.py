import time


def activate_zone(zone_id, duration):
    print(f"[GPIO] Activating zone {zone_id} for {duration} seconds...")
    # Replace with actual GPIO logic
    time.sleep(duration)
    print(f"[GPIO] Zone {zone_id} watering complete.")