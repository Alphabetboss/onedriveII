# ii_pins.py
# Choose how you’re specifying pins: "BCM" or "BOARD"
PIN_MODE = "BCM"           # change to "BOARD" if you meant physical header pins

# Your valve pins, in the numbering scheme above:
VALVE_PINS = [3, 6, 11]

# Most relay boards are ACTIVE-LOW (IN=LOW -> relay ON). Set True for that.
ACTIVE_LOW = True
