# gpio_pulse.py
# Usage sudo python3 gpio_pulse.py bcm_pin seconds [--active-low]
# Example sudo python3 gpio_pulse.py 17 30 --active-low
import sys, time
import RPi.GPIO as GPIO

if len(sys.argv)  3
    print(Usage sudo python3 gpio_pulse.py bcm_pin seconds [--active-low])
    sys.exit(1)

pin = int(sys.argv[1])
secs = float(sys.argv[2])
active_low = (--active-low in sys.argv)

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH if active_low else GPIO.LOW)

def set_on(on bool)
    GPIO.output(pin, GPIO.LOW if (on and active_low) else GPIO.HIGH if active_low else GPIO.HIGH if not on else GPIO.LOW)

try
    print(fValve ON (pin {pin}) for {secs}s...)
    set_on(True)
    time.sleep(secs)
    print(Valve OFF)
    set_on(False)
finally
    GPIO.cleanup()