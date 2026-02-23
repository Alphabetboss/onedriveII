# os_run_zone.py
# Usage: python os_run_zone.py <OS_IP_OR_HOST> <plain_password> <zone_index> <seconds>
# Example: python os_run_zone.py 192.168.1.50 opendoor 0 60
import sys, hashlib, json, requests

host = sys.argv[1]            # e.g. "192.168.1.50" or "raspberrypi.local:8080"
pw_plain = sys.argv[2]        # OpenSprinkler device password (plain text)
zone = int(sys.argv[3])       # 0-based
seconds = int(sys.argv[4])    # duration

pw_md5 = hashlib.md5(pw_plain.encode()).hexdigest().lower()
base = f"http://{host}"

# Optional: discover station count from /ja (Get JSON All)
try:
    ja = requests.get(f"{base}/ja", params={"pw": pw_md5}, timeout=5).json()
    # Derive station count; fall back to 16 if not obvious
    nstations = ja.get("nstations") or len(ja.get("stations", {}).get("sn", [])) or 16
except Exception:
    nstations = 16

dur = [0]*nstations
if zone >= nstations: raise SystemExit(f"Zone {zone} out of range (nstations={nstations})")
dur[zone] = seconds

# Run-Once Program: /cr?t=[durations]
r = requests.get(f"{base}/cr", params={"pw": pw_md5, "t": json.dumps(dur)}, timeout=5)
print("HTTP", r.status_code, r.text)
