# post_hydration_test.py
import requests, time, json
payload = {
  "timestamp":"2025-09-06T00:00:00Z",
  "green_coverage":0.32,
  "dead_grass_pct":0.0,
  "standing_water": False,
  "puddles_conf": 0.0,
  "detections": []
}
url = "http://127.0.0.1:5051/api/hydration"
r = requests.post(url, json=payload, timeout=5)
print("POST", r.status_code, r.text)
