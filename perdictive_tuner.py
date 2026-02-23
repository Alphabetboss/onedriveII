# predictive_tuner.py

class PredictiveTuner:
    def __init__(self, memory):
        self.memory = memory  # zone_memory from evaluator

    def suggest_adjustment(self, zone_id):
        history = self.memory.get(zone_id, [])
        if len(history) < 3:
            return None  # Not enough data

        # Analyze last 3 results
        deltas = []
        for i in range(1, 3):
            prev = history[-i - 1]
            curr = history[-i]
            delta = curr["green"] - prev["green"]
            deltas.append(delta)

        avg_delta = sum(deltas) / len(deltas)
        if avg_delta < 0:
            return "Increase watering next time"
        elif avg_delta > 0:
            return "Decrease watering slightly"
        else:
            return "Keep watering constant"