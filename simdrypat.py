# Simulated dry patch detection
dry_patch_detected = True  # This would normally come from your grass health analysis

def should_activate_sprinkler(dry_patch_detected, cooldown_active):
    if dry_patch_detected and not cooldown_active:
        return True
    return False

# Simulate cooldown logic
cooldown_active = False  # Toggle this to True to simulate cooldown blocking

if should_activate_sprinkler(dry_patch_detected, cooldown_active):
    print("Sprinkler ON: Dry patch detected.")
else:
    print("Sprinkler OFF: Conditions not met.")