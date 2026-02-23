# dashboard.py

from flask import Flask, render_template, request
from health_evaluator import ZoneHealthEvaluator
from water_adjuster import WaterAdjuster

app = Flask(__name__)
evaluator = ZoneHealthEvaluator()
adjuster = WaterAdjuster()

@app.route("/")
def home():
    zones = ["zone_1", "zone_2", "zone_3"]
    data = [evaluator.get_last_result(z) for z in zones]
    return render_template("dashboard.html", zones=data)

@app.route("/override", methods=["POST"])
def override():
    zone_id = request.form["zone"]
    duration = float(request.form["duration"])
    # Trigger manual watering here
    return f"Manual override: {zone_id} watered for {duration} mins"

if __name__ == "__main__":
    app.run(debug=True)