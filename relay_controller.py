# relay_controller.py â€” safe, GPIO-optional
from __future__ import annotations
import os, time

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False

RELAY_PIN = int(os.getenv('II_RELAY_PIN','17'))

def setup():
    if _HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
    return _HAS_GPIO

def water_for(seconds: float = 10.0):
    if _HAS_GPIO:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(max(0.0, seconds))
        GPIO.output(RELAY_PIN, GPIO.LOW)
        return {'status':'ok','pin':RELAY_PIN,'seconds':seconds,'gpio':True}
    else:
        # Simulate for dev machines
        time.sleep(min(0.1, seconds))
        return {'status':'simulated','pin':RELAY_PIN,'seconds':seconds,'gpio':False}