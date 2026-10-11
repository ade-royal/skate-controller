"""Pi send-policy tests. The fake sensor never opens I2C."""

from __future__ import annotations

import unittest

from controller.movement import MovementConfig
from scripts.pi_sender import read_state


class FakeSensor:
    def __init__(self, acceleration=None, error: str | None = None) -> None:
        self._acceleration = acceleration
        self._error = error

    def get_acceleration(self) -> dict[str, float]:
        if self._error is not None:
            raise OSError(self._error)
        return self._acceleration


class ReadStateTests(unittest.TestCase):
    def test_failed_sensor_read_sends_center(self) -> None:
        state, acceleration, error = read_state(FakeSensor(error="i2c bus"), MovementConfig())
        self.assertEqual(state, "CENTER")
        self.assertIsNone(acceleration)
        self.assertEqual(error, "i2c bus")

    def test_measured_left_lean_sends_left(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": -0.045, "z": 1.0})
        state, acceleration, error = read_state(sensor, MovementConfig())
        self.assertEqual(state, "LEFT")
        self.assertEqual(acceleration["y"], -0.045)
        self.assertIsNone(error)

    def test_measured_right_lean_sends_right(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": 0.045, "z": 1.0})
        state, _, error = read_state(sensor, MovementConfig())
        self.assertEqual(state, "RIGHT")
        self.assertIsNone(error)

    def test_neutral_sends_center(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": 0.008, "z": 1.0})
        state, _, error = read_state(sensor, MovementConfig())
        self.assertEqual(state, "CENTER")
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
