"""Board orientation from accel + gyro using a complementary filter."""

from __future__ import annotations

import math

DEFAULT_ALPHA = 0.98
# When total acceleration strays this far from 1 g (pops, landings, pushes),
# the accelerometer is not measuring gravity, so trust the gyro alone.
GRAVITY_TRUST_BAND_G = 0.25


def accel_angles(ax: float, ay: float, az: float) -> tuple[float, float]:
    """Roll and pitch in degrees implied by gravity alone."""
    roll = math.degrees(math.atan2(ay, az))
    pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
    return roll, pitch


class ComplementaryFilter:
    """Tracks roll/pitch (drift-corrected) and yaw (gyro-integrated, drifts)."""

    def __init__(self, alpha: float = DEFAULT_ALPHA):
        self.alpha = alpha
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self._initialized = False

    def reset(self) -> None:
        self._initialized = False
        self.yaw = 0.0

    def update(
        self, ax: float, ay: float, az: float, gx: float, gy: float, gz: float, dt: float
    ) -> tuple[float, float, float]:
        acc_roll, acc_pitch = accel_angles(ax, ay, az)
        if not self._initialized:
            self.roll, self.pitch = acc_roll, acc_pitch
            self._initialized = True
            return self.roll, self.pitch, self.yaw

        self.roll += gx * dt
        self.pitch += gy * dt
        self.yaw += gz * dt

        magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        if abs(magnitude - 1.0) < GRAVITY_TRUST_BAND_G:
            k = 1.0 - self.alpha
            self.roll += k * _angle_diff(acc_roll, self.roll)
            self.pitch += k * _angle_diff(acc_pitch, self.pitch)
        return self.roll, self.pitch, self.yaw


def _angle_diff(target: float, current: float) -> float:
    """Shortest signed difference target - current, in degrees."""
    return (target - current + 180.0) % 360.0 - 180.0
