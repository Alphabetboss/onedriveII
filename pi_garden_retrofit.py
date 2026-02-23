#!/usr/bin/env python3
"""
Ingenious Irrigation - Retrofit Controller (pass-through by default)
- Relays are wired COM->IN, NC->OUT (fail-safe pass-through)
- Energize relay to BLOCK a zone (open circuit)
- Optional AC-detect inputs tell us when legacy controller is calling a zone
"""

import time
import json
import signal
import sys
from datetime import datetime, timedelta

import RPi.GPIO as GPIO

# ------------------ CONFIG ------------------
# BCM pins for 8 relay outputs (order = Zone 1..8)
RELAY_PINS = [5, 6, 13, 19, 26, 16, 20, 21]

# Optional AC-detect inputs (H11AA1 -> transistor to GND, with pull-up): LOW = AC present
# Use None for zones you didn't build a detector for.
DETECT_PINS = [17, 27, 22, None, None, None, None, None]

# Fail-safe wiring: NC = pass-through. Set this to True if your relay board INVERTS logic (LOW=on).
RELAY_ACTIVE_LOW = True  # most 5V opto relay boards are active LOW

# Decision policy (placeholder): Always allow unless overridden by schedule / AI file flags.
# You can flip these flags live by writing schedule_overrides.json.
OVERRIDE_FILE = "/home/pi/retrofit/schedule_overrides.json"

# If we choose to shorten a run, how long to allow before blocking (seconds)
DEFAULT_SHORTEN_SECS = 60  # 1 minute for bench tests; change later

LOG_FILE = "/home/pi/retrofit/retrofit_events.log"

# ------------------ GPIO SETUP ------------------
GPIO.setmode(GPIO.BCM)
for pin in RELAY_PINS:
    GPIO.setup(pin, GPIO.OUT)
    # Default state: DE-ENERGIZED so NC path is connected (pass-through)
    if RELAY_ACTIVE_LOW:
        GPIO.output(pin, GPIO.HIGH)
    else:
        GPIO.output(pin, GPIO.LOW)

for pin in DETECT_PINS:
    if pin is not None:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ------------------ HELPERS ------------------


def log_event(msg: str):
    line = f"{datetime.now().isoformat()} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def set_relay(zone_idx: int, block: bool):
    """block=True energizes relay to OPEN (stop water); block=False de-energizes (pass-through)"""
    pin = RELAY_PINS[zone_idx]
    if RELAY_ACTIVE_LOW:
        GPIO.output(pin, GPIO.LOW if block else GPIO.HIGH)
    else:
        GPIO.output(pin, GPIO.HIGH if block else GPIO.LOW)


def read_overrides():
    """Read override policy from JSON, e.g.:
    {
      "global_skip": false,
      "zones": {
        "1": {"skip": false, "shorten_secs": 0},
        "2": {"skip": true},
        "3": {"shorten_secs": 300}
      }
    }
    """
    try:
        with open(OVERRIDE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"global_skip": False, "zones": {}}


def is_legacy_calling(zone_idx: int) -> bool:
    """Return True if AC present on that zone (legacy controller is commanding it)."""
    pin = DETECT_PINS[zone_idx]
    if pin is None:
        # If no detector, we can infer by time/sequence or just return False to let it pass.
        return False
    # LOW = AC present (optocoupler pulling down)
    return GPIO.input(pin) == GPIO.LOW

# Make sure we never block two zones incorrectly (legacy controllers usually run 1 at a time)


def block_all_except(zone_idx: int):
    for i in range(len(RELAY_PINS)):
        set_relay(i, block=False if i == zone_idx else False)


def graceful_exit(*_):
    log_event("Exiting, restoring pass-through on all zones.")
    for i in range(len(RELAY_PINS)):
        set_relay(i, block=False)
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

# ------------------ MAIN LOOP ------------------
log_event("Retrofit controller started (fail-safe pass-through).")

# Track shorten timers: when legacy starts a zone, we may stop it early
shorten_deadlines = {}  # zone_idx -> datetime

POLL_SEC = 0.1
while True:
    overrides = read_overrides()
    global_skip = overrides.get("global_skip", False)
    zone_over = overrides.get("zones", {})

    for z in range(len(RELAY_PINS)):
        calling = is_legacy_calling(z)

        # Default: allow pass-through
        desired_block = False

        # Apply overrides
        zconf = zone_over.get(str(z + 1), {})
        z_skip = zconf.get("skip", False) or global_skip
        z_shorten = int(zconf.get("shorten_secs", 0) or 0)
        if z_shorten <= 0:
            z_shorten = DEFAULT_SHORTEN_SECS  # bench default; tune later

        if calling:
            if z not in shorten_deadlines:
                # New call observed
                shorten_deadlines[z] = datetime.now(
                ) + timedelta(seconds=z_shorten)
                log_event(
                    f"Zone {z+1}: legacy ON detected; shorten deadline at {shorten_deadlines[z].time()}")

            if z_skip:
                desired_block = True
            else:
                # allow until deadline
                if datetime.now() >= shorten_deadlines[z]:
                    desired_block = True
        else:
            # Not calling; clear deadline and pass-through
            if z in shorten_deadlines:
                del shorten_deadlines[z]
            desired_block = False

        set_relay(z, block=desired_block)

    time.sleep(POLL_SEC)