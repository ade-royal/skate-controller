"""Movement decision helpers."""


def resolve_movement(reading, threshold=1000):
    """Resolve a movement command from calibrated readings."""
    if reading.get("accel_y", 0) > threshold:
        return "forward"
    if reading.get("accel_y", 0) < -threshold:
        return "backward"
    if reading.get("accel_x", 0) > threshold:
        return "left"
    if reading.get("accel_x", 0) < -threshold:
        return "right"
    return "idle"
