"""Ollie event tests. No MPU-6050 and no keyboard required."""

from __future__ import annotations

import unittest

from controller.movement import RIGHT, classify_movement
from controller.ollie import OLLIE, OllieConfig, OllieDetector


def acceleration(x: float = 0.0, y: float = 0.0, z: float = 1.0) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


class OllieDetectorTests(unittest.TestCase):
    def test_defaults(self) -> None:
        config = OllieConfig()
        self.assertEqual(config.threshold, 0.300)
        self.assertEqual(config.cooldown, 0.40)

    def test_threshold_is_inclusive(self) -> None:
        detector = OllieDetector()
        self.assertIsNone(detector.update(0.299, 0.0))
        self.assertEqual(detector.update(0.300, 0.1), OLLIE)

    def test_negative_x_is_not_an_ollie(self) -> None:
        self.assertIsNone(OllieDetector().update(-0.500, 0.0))

    def test_consecutive_samples_above_the_threshold_fire_once(self) -> None:
        detector = OllieDetector()
        self.assertEqual(detector.update(0.300, 0.0), OLLIE)
        self.assertIsNone(detector.update(0.800, 0.1))
        self.assertIsNone(detector.update(0.450, 0.2))

    def test_must_drop_below_the_threshold_and_wait_out_the_cooldown(self) -> None:
        detector = OllieDetector(OllieConfig(cooldown=0.40))
        self.assertEqual(detector.update(0.300, 0.0), OLLIE)
        self.assertIsNone(detector.update(0.100, 0.2))
        self.assertIsNone(detector.update(0.500, 0.3))
        self.assertIsNone(detector.update(0.500, 0.45))
        self.assertIsNone(detector.update(0.000, 0.50))
        self.assertEqual(detector.update(0.300, 0.60), OLLIE)

    def test_right_lean_stays_right_when_x_crosses_the_ollie_gate(self) -> None:
        reading = acceleration(x=0.300, y=0.045)
        self.assertEqual(classify_movement(reading), RIGHT)
        self.assertEqual(OllieDetector().update(reading["x"], 0.0), OLLIE)

    def test_arm_status_follows_the_existing_latch(self) -> None:
        detector = OllieDetector(OllieConfig(cooldown=0.40))
        self.assertEqual(detector.arm_status(0.0, above=False), "armed")
        self.assertEqual(detector.update(0.300, 0.0), OLLIE)
        self.assertEqual(detector.arm_status(0.0, above=True), "cooldown 0.40s")
        self.assertIsNone(detector.update(0.100, 0.10))
        self.assertEqual(detector.arm_status(0.10, above=False), "below gate, cooldown 0.30s")
        held = OllieDetector(OllieConfig(cooldown=0.40))
        self.assertEqual(held.update(0.300, 0.0), OLLIE)
        self.assertIsNone(held.update(0.500, 0.50))
        self.assertEqual(held.arm_status(0.50, above=True), "above gate, drop below 0.300 to re-arm")

    def test_invalid_settings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OllieConfig(threshold=0)
        with self.assertRaises(ValueError):
            OllieConfig(cooldown=-0.1)


if __name__ == "__main__":
    unittest.main()
