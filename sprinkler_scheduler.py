# sprinkler_scheduler.py

from health_evaluator import ZoneHealthEvaluator
from water_adjuster import WaterAdjuster
from sensor_checker import SensorChecker  # We'll build this next
import time

class SprinklerScheduler:
    def __init__(self):
        self.evaluator = ZoneHealthEvaluator()
        self.adjuster = WaterAdjuster()
        self.sensor = SensorChecker()

        # Define your zones and base durations
        self.zones = {
            "zone_1": {"base_duration": 30},
            "zone_2": {"base_duration": 45},
            "zone_3": {"base_duration": 20}
        }

    def run_daily_schedule(self):
        print("ðŸŒ… Starting daily sprinkler schedule...\n")

        for zone_id, config in self.zones.items():
            print(f"ðŸ” Evaluating {zone_id}...")

            # Get health data (from camera analysis or stored metrics)
            green, yellow, brown = self.sensor.get_zone_health(zone_id)
            sensors = self.sensor.get_zone_sensors(zone_id)

            # Evaluate health
            zone_eval = self.evaluator.evaluate_zone(
                zone_id=zone_id,
                green=green,
                yellow=yellow,
                brown=brown,
                sensors=sensors
            )

            # Adjust watering
            watering_plan = self.adjuster.adjust_watering(zone_eval)

            # Trigger watering (or skip)
            if watering_plan["final_duration"] > 0:
                print(f"ðŸ’§ Watering {zone_id} for {watering_plan['final_duration']} mins")
                self.sensor.activate_sprinkler(zone_id, watering_plan["final_duration"])
            else:
                print(f"ðŸš« Skipping {zone_id}: {watering_plan['override_reason']}")

            print("â€”" * 40)

        print("âœ… Schedule complete.\n")

# Optional: run daily
if __name__ == "__main__":
    scheduler = SprinklerScheduler()
    scheduler.run_daily_schedule()