# Mock GPIO control (replace with actual RPi.GPIO or gpiozero when Pi is back)
class MockRelay:
    def __init__(self):
        self.state = "OFF"

    def activate(self):
        self.state = "ON"
        print("Relay activated: Sprinkler ON")

    def deactivate(self):
        self.state = "OFF"
        print("Relay deactivated: Sprinkler OFF")

# Simulate relay control
relay = MockRelay()

# Trigger based on dry patch
if dry_patch_detected:
    relay.activate()
else:
    relay.deactivate()