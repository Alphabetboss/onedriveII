import requests

url = "http://localhost:5000/voice/trigger"
payload = {"transcript": "How much water does zone 2 need?"}

res = requests.post(url, json=payload)
print("Response:", res.json())