"""Pi send-policy tests. The fake sensor never opens I2C."""

from __future__ import annotations

import unittest

from controller.movement import MovementConfig
from controller.ollie import OllieConfig, OllieDetector
from scripts.pi_sender import _format_frame, read_state


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
        state, acceleration, error, event = read_state(
            FakeSensor(error="i2c bus"), MovementConfig(), OllieDetector(), 0.0
        )
        self.assertEqual(state, "CENTER")
        self.assertIsNone(acceleration)
        self.assertEqual(error, "i2c bus")
        self.assertIsNone(event)

    def test_measured_left_lean_sends_left(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": -0.045, "z": 1.0})
        state, acceleration, error, event = read_state(sensor, MovementConfig(), OllieDetector(), 0.0)
        self.assertEqual(state, "LEFT")
        self.assertEqual(acceleration["y"], -0.045)
        self.assertIsNone(error)
        self.assertIsNone(event)

    def test_measured_right_lean_sends_right(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": 0.045, "z": 1.0})
        state, _, error, event = read_state(sensor, MovementConfig(), OllieDetector(), 0.0)
        self.assertEqual(state, "RIGHT")
        self.assertIsNone(error)
        self.assertIsNone(event)

    def test_neutral_sends_center(self) -> None:
        sensor = FakeSensor({"x": 0.0, "y": 0.008, "z": 1.0})
        state, _, error, event = read_state(sensor, MovementConfig(), OllieDetector(), 0.0)
        self.assertEqual(state, "CENTER")
        self.assertIsNone(error)
        self.assertIsNone(event)

    def test_ollie_while_leaning_right_keeps_right(self) -> None:
        sensor = FakeSensor({"x": 0.300, "y": 0.045, "z": 1.0})
        detector = OllieDetector()
        state, _, error, event = read_state(sensor, MovementConfig(), detector, 0.0)
        self.assertEqual(state, "RIGHT")
        self.assertEqual(event, "OLLIE")
        self.assertIsNone(error)
        later, _, _, later_event = read_state(sensor, MovementConfig(), detector, 0.1)
        self.assertEqual(later, "RIGHT")
        self.assertIsNone(later_event)

    def test_panel_keeps_the_gate_and_the_sent_ollie(self) -> None:
        panel = _format_frame(
            {"x": 0.300, "y": 0.045, "z": 1.0},
            "RIGHT",
            "OLLIE",
            MovementConfig(),
            OllieConfig(),
            "cooldown 0.40s",
            "FIRED and SENT  X +0.300 g  RIGHT | OLLIE",
            "127.0.0.1",
            5050,
        )
        self.assertIn("STATE      RIGHT", panel)
        self.assertIn("X            +0.300 g   ABOVE 0.300", panel)
        self.assertIn("ARM        cooldown 0.40s", panel)
        self.assertIn("THIS       OLLIE fired and sent", panel)
        self.assertIn("LAST       FIRED and SENT  X +0.300 g  RIGHT | OLLIE", panel)


if __name__ == "__main__":
    unittest.main()
