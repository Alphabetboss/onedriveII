"""
gpio_driver.py â€” Raspberry Pi GPIO abstraction with safe fallbacks.
- Works on real Pi (RPi.GPIO) or on laptops for dev (MockGPIO).
- Active level is configurable for your specific relay board.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import time

try:
    import RPi.GPIO as RPI
    _ON_PI = True
except Exception:  # dev machine fallback
    _ON_PI = False

    class MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        LOW = 0
        HIGH = 1
        _pins = {}

        @classmethod
        def setwarnings(cls, flag): pass
        @classmethod
        def setmode(cls, mode): pass
        @classmethod
        def setup(cls, pin, mode): cls._pins[pin] = cls.LOW
        @classmethod
        def output(cls, pin, val): cls._pins[pin] = val
        @classmethod
        def cleanup(cls): cls._pins.clear()

    RPI = MockGPIO  # type: ignore


@dataclass
class PinConfig:
    zone_pins: Dict[int, int]  # {zone_number: BCM_pin}
    active_high: bool = False  # Most relay boards are active-LOW
    startup_all_off: bool = True


class GPIODriver:
    def __init__(self, cfg: PinConfig):
        self.cfg = cfg
        RPI.setwarnings(False)
        RPI.setmode(RPI.BCM)
        for pin in cfg.zone_pins.values():
            RPI.setup(pin, RPI.OUT)
        if cfg.startup_all_off:
            self.all_off()

    def _on_level(self):
        return RPI.HIGH if self.cfg.active_high else RPI.LOW

    def _off_level(self):
        return RPI.LOW if self.cfg.active_high else RPI.HIGH

    def set_zone(self, zone: int, on: bool) -> None:
        pin = self.cfg.zone_pins.get(zone)
        if pin is None:
            raise ValueError(f"Unknown zone {zone}")
        RPI.output(pin, self._on_level() if on else self._off_level())

    def pulse_zone(self, zone: int, seconds: float) -> None:
        self.set_zone(zone, True)
        try:
            time.sleep(max(0.0, seconds))
        finally:
            self.set_zone(zone, False)

    def all_off(self) -> None:
        for z in self.cfg.zone_pins:
            self.set_zone(z, False)

    def cleanup(self) -> None:
        try:
            self.all_off()
        finally:
            RPI.cleanup()

    def snapshot(self) -> Dict[int, int]:
        # On a real Pi we donâ€™t have simple readback on output pins; return last intents.
        # For Mock, return internal map.
        if hasattr(RPI, "_pins"):
            return {z: RPI._pins[self.cfg.zone_pins[z]] for z in self.cfg.zone_pins}
        return {z: -1 for z in self.cfg.zone_pins}  # unknown