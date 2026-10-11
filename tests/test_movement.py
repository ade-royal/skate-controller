"""Movement classification tests. No MPU-6050 required."""

from __future__ import annotations

import unittest

from controller.movement import (
    CENTER,
    LEFT,
    RIGHT,
    MovementConfig,
    adjusted_steering,
    classify_movement,
    classify_steering,
)


def acceleration(x: float = 0.0, y: float = 0.0, z: float = 1.0) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


class ClassifySteeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MovementConfig(
            steering_axis="x",
            center_offset=0.0,
            left_threshold=-0.20,
            right_threshold=0.20,
            dead_zone=0.08,
        )

    def test_negative_lean_is_left(self) -> None:
        self.assertEqual(classify_steering(-0.50, self.config), LEFT)

    def test_positive_lean_is_right(self) -> None:
        self.assertEqual(classify_steering(0.50, self.config), RIGHT)

    def test_small_lean_is_center(self) -> None:
        self.assertEqual(classify_steering(0.02, self.config), CENTER)
        self.assertEqual(classify_steering(-0.02, self.config), CENTER)
        self.assertEqual(classify_steering(0.0, self.config), CENTER)

    def test_left_threshold_boundary_is_left(self) -> None:
        self.assertEqual(classify_steering(-0.20, self.config), LEFT)

    def test_just_short_of_left_threshold_is_center(self) -> None:
        self.assertEqual(classify_steering(-0.199, self.config), CENTER)

    def test_right_threshold_boundary_is_right(self) -> None:
        self.assertEqual(classify_steering(0.20, self.config), RIGHT)

    def test_just_short_of_right_threshold_is_center(self) -> None:
        self.assertEqual(classify_steering(0.199, self.config), CENTER)

    def test_dead_zone_edges_are_center(self) -> None:
        self.assertEqual(classify_steering(-0.08, self.config), CENTER)
        self.assertEqual(classify_steering(0.08, self.config), CENTER)

    def test_between_dead_zone_and_threshold_is_center(self) -> None:
        self.assertEqual(classify_steering(-0.10, self.config), CENTER)
        self.assertEqual(classify_steering(0.10, self.config), CENTER)


class MeasuredLeanTests(unittest.TestCase):
    """Default config checked against the first mounted-board Y readings."""

    def setUp(self) -> None:
        self.config = MovementConfig()

    def test_defaults_match_the_first_board_test(self) -> None:
        self.assertEqual(self.config.steering_axis, "y")
        self.assertEqual(self.config.center_offset, 0.008)
        self.assertEqual(self.config.left_threshold, -0.053)
        self.assertEqual(self.config.right_threshold, 0.037)
        self.assertEqual(self.config.dead_zone, 0.018)

    def test_neutral_y_is_center(self) -> None:
        self.assertEqual(classify_movement(acceleration(y=0.008), self.config), CENTER)

    def test_normal_and_extreme_left_are_left(self) -> None:
        self.assertEqual(classify_movement(acceleration(y=-0.045), self.config), LEFT)
        self.assertEqual(classify_movement(acceleration(y=-0.075), self.config), LEFT)

    def test_normal_and_extreme_right_are_right(self) -> None:
        self.assertEqual(classify_movement(acceleration(y=0.045), self.config), RIGHT)
        self.assertEqual(classify_movement(acceleration(y=0.075), self.config), RIGHT)

    def test_small_wobble_around_neutral_is_center(self) -> None:
        # Adjusted values are +0.010 g and -0.010 g, inside the 0.018 dead zone.
        self.assertEqual(classify_movement(acceleration(y=0.018), self.config), CENTER)
        self.assertEqual(classify_movement(acceleration(y=-0.002), self.config), CENTER)

    def test_lean_short_of_normal_is_center(self) -> None:
        # Adjusted -0.028 g and +0.022 g are outside the dead zone and short of a turn.
        self.assertEqual(classify_movement(acceleration(y=-0.020), self.config), CENTER)
        self.assertEqual(classify_movement(acceleration(y=0.030), self.config), CENTER)

    def test_other_axes_do_not_steer(self) -> None:
        reading = acceleration(x=-0.50, y=0.008, z=0.50)
        self.assertEqual(classify_movement(reading, self.config), CENTER)


class ClassifyMovementTests(unittest.TestCase):
    def test_uses_configured_axis(self) -> None:
        config = MovementConfig(steering_axis="y")
        reading = acceleration(x=0.0, y=-0.50, z=1.0)
        self.assertEqual(classify_movement(reading, config), LEFT)

        reading = acceleration(x=-0.50, y=0.0, z=1.0)
        self.assertEqual(classify_movement(reading, config), CENTER)

    def test_z_axis_can_be_selected(self) -> None:
        config = MovementConfig(steering_axis="z")
        self.assertEqual(classify_movement(acceleration(z=0.50), config), RIGHT)

    def test_inverted_axis_flips_direction(self) -> None:
        config = MovementConfig(steering_axis="-x")
        self.assertEqual(classify_movement(acceleration(x=0.50), config), LEFT)
        self.assertEqual(classify_movement(acceleration(x=-0.50), config), RIGHT)

    def test_center_offset_shifts_neutral(self) -> None:
        config = MovementConfig(steering_axis="x", center_offset=0.25)
        self.assertEqual(classify_movement(acceleration(x=0.25), config), CENTER)
        self.assertEqual(classify_movement(acceleration(x=0.0), config), LEFT)
        self.assertEqual(classify_movement(acceleration(x=0.50), config), RIGHT)

    def test_adjusted_steering_applies_sign_and_offset(self) -> None:
        config = MovementConfig(steering_axis="-y", center_offset=0.10)
        steering = adjusted_steering(acceleration(y=0.40), config)
        self.assertAlmostEqual(steering, -0.50)

    def test_missing_axis_raises(self) -> None:
        config = MovementConfig(steering_axis="x")
        with self.assertRaises(KeyError):
            classify_movement({"y": 0.0}, config)

    def test_unknown_steering_axis_raises(self) -> None:
        with self.assertRaises(ValueError):
            MovementConfig(steering_axis="roll")

    def test_threshold_inside_dead_zone_raises(self) -> None:
        with self.assertRaises(ValueError):
            MovementConfig(left_threshold=-0.05, dead_zone=0.08)

        with self.assertRaises(ValueError):
            MovementConfig(right_threshold=0.05, dead_zone=0.08)


if __name__ == "__main__":
    unittest.main()
