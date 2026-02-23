# hardware/relay.py
import os
class _Dummy:
    def on(self, zone:int): print(f"[SIM] ON zone {zone}")
    def off(self, zone:int): print(f"[SIM] OFF zone {zone}")

def _is_pi():
    return os.uname().machine.startswith("arm") if hasattr(os, "uname") else False

if _is_pi():
    # from gpiozero import OutputDevice  # real implementation
    class ZoneController:
        def __init__(self): pass # map pins per zone
        def on(self, zone:int): pass
        def off(self, zone:int): pass
else:
    class ZoneController(_Dummy): pass
