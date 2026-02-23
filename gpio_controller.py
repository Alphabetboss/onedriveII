import RPi.GPIO as GPIO

class GPIOController:
    def __init__(self, pin_map):
        GPIO.setmode(GPIO.BCM)
        self.pins = pin_map
        for pin in self.pins.values():
            GPIO.setup(pin, GPIO.OUT)

    def activate_zone(self, zone):
        GPIO.output(self.pins[zone], GPIO.HIGH)

    def deactivate_zone(self, zone):
        GPIO.output(self.pins[zone], GPIO.LOW)