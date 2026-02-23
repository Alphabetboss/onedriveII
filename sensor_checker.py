# sensor_checker.py

import random

class SensorChecker:
    def get_zone_health(self, zone_id):
        """
        Simulate or fetch health data from camera analysis.
        Returns: green %, yellow %, brown %
        """
        # Replace with real image analysis later
        green = random.randint(60, 100)
        yellow = random.randint(0, 30)
        brown = random.randint(0, 10)
        return green, yellow, brown

    def get_zone_sensors(self, zone_id):
        """
        Simulate or fetch sensor data.
        Returns: dict with rain/puddle detection
        """
        # Replace with GPIO or API calls later
        return {
            "rain_detected": random.choice([False, False, True]),
            "puddle_detected": random.choice([False, False, True])
        }

    def activate_sprinkler(self, zone_id, duration):
        """
        Trigger GPIO relay or send command to sprinkler system.
        """
        print(f"ðŸŸ¢ Sprinkler ON for {zone_id} â€” {duration} mins")
        # Replace with actual GPIO control