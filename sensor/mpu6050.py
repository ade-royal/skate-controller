"""MPU6050 sensor access helpers."""


class MPU6050:
    """Minimal MPU6050 sensor abstraction."""

    def __init__(self, bus=None, address=0x68):
        self.bus = bus
        self.address = address

    def read_raw(self):
        """Return raw accelerometer/gyroscope readings."""
        return {
            "accel_x": 0,
            "accel_y": 0,
            "accel_z": 0,
            "gyro_x": 0,
            "gyro_y": 0,
            "gyro_z": 0,
        }
