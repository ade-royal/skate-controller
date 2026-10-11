"""Calibration, hysteresis, squat, and hand tests. No webcam required."""

from __future__ import annotations

import math
import unittest

from vision.pose import (
    BOTH_HANDS_UP,
    HAND_DOWN,
    HAND_UP,
    LANDMARK_COUNT,
    LEFT_ANKLE,
    LEFT_HAND_UP,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ANKLE,
    RIGHT_HAND_UP,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    SIDE_LEFT,
    SIDE_NONE,
    SIDE_RIGHT,
    SQUAT,
    STANDING,
    UNKNOWN,
    Landmark,
    PoseConfig,
    PoseSession,
    hand_rise,
    joint_angle_degrees,
    knee_crouch_degrees,
    latch_update,
    measure_pose,
    select_leg_side,
)


ASPECT = 1.0
LEFT_LEG = (LEFT_HIP, LEFT_KNEE, LEFT_ANKLE)
RIGHT_LEG = (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE)


def empty_pose() -> list[Landmark]:
    return [Landmark(0.0, 0.0, visibility=0.0) for _ in range(LANDMARK_COUNT)]


def standing_pose() -> list[Landmark]:
    """Neutral stance in the middle of the frame. Aspect 1 keeps the math obvious."""
    pose = empty_pose()
    pose[LEFT_SHOULDER] = Landmark(0.40, 0.30)
    pose[RIGHT_SHOULDER] = Landmark(0.60, 0.30)
    pose[LEFT_WRIST] = Landmark(0.32, 0.58)
    pose[RIGHT_WRIST] = Landmark(0.68, 0.58)
    pose[LEFT_HIP] = Landmark(0.42, 0.55)
    pose[RIGHT_HIP] = Landmark(0.58, 0.55)
    pose[LEFT_KNEE] = Landmark(0.42, 0.75)
    pose[RIGHT_KNEE] = Landmark(0.58, 0.75)
    pose[LEFT_ANKLE] = Landmark(0.42, 0.95)
    pose[RIGHT_ANKLE] = Landmark(0.58, 0.95)
    return pose


def with_hips(pose: list[Landmark], hip_y: float) -> list[Landmark]:
    """Move both hips to hip_y and keep the knees on the straight hip-ankle line."""
    updated = list(pose)
    for hip, knee, ankle, x in (
        (LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, 0.42),
        (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, 0.58),
    ):
        ankle_y = updated[ankle].y
        updated[hip] = Landmark(x, hip_y)
        updated[knee] = Landmark(x, (hip_y + ankle_y) / 2)
    return updated


def bend_knee(
    pose: list[Landmark], hip_index: int, knee_index: int, ankle_index: int, bend_degrees: float
) -> list[Landmark]:
    """Bend one knee by moving the hip. 0 degrees stays straight."""
    updated = list(pose)
    knee = updated[knee_index]
    ankle = updated[ankle_index]
    bend = math.radians(bend_degrees)
    vx = knee.x - ankle.x
    vy = knee.y - ankle.y
    cosine = math.cos(bend)
    sine = math.sin(bend)
    updated[hip_index] = Landmark(
        knee.x + vx * cosine - vy * sine,
        knee.y + vx * sine + vy * cosine,
        knee.z,
        knee.visibility,
    )
    return updated


def bend_both(pose: list[Landmark], bend_degrees: float) -> list[Landmark]:
    pose = bend_knee(pose, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, bend_degrees)
    return bend_knee(pose, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, bend_degrees)


def set_visibility(pose: list[Landmark], indexes: tuple[int, ...], visibility: float) -> list[Landmark]:
    updated = list(pose)
    for index in indexes:
        point = updated[index]
        updated[index] = Landmark(point.x, point.y, point.z, visibility)
    return updated


def with_wrist(pose: list[Landmark], index: int, wrist_y: float) -> list[Landmark]:
    updated = list(pose)
    updated[index] = Landmark(updated[index].x, wrist_y)
    return updated


def hide(pose: list[Landmark], index: int) -> list[Landmark]:
    updated = list(pose)
    point = updated[index]
    updated[index] = Landmark(point.x, point.y, point.z, visibility=0.1)
    return updated


def shift(pose: list[Landmark], x: float, y: float, scale: float = 1.0) -> list[Landmark]:
    return [
        Landmark(point.x * scale + x, point.y * scale + y, point.z * scale, point.visibility)
        for point in pose
    ]


def calibrated_session() -> tuple[PoseSession, list[Landmark]]:
    session = PoseSession()
    neutral = standing_pose()
    session.start_calibration(0.0)
    session.update(neutral, ASPECT, 2.5)
    session.update(neutral, ASPECT, 3.0)
    return session, neutral


class MeasurementTests(unittest.TestCase):
    def test_straight_leg_is_about_180_degrees(self) -> None:
        sample = measure_pose(standing_pose(), ASPECT)
        self.assertAlmostEqual(sample.left_knee_angle_degrees or 0, 180, delta=0.1)
        self.assertAlmostEqual(sample.right_knee_angle_degrees or 0, 180, delta=0.1)

    def test_crouch_is_extra_bend_past_the_calibrated_angle(self) -> None:
        self.assertAlmostEqual(knee_crouch_degrees(170, 180), 10)
        self.assertIsNone(knee_crouch_degrees(170, None))
        self.assertIsNone(knee_crouch_degrees(None, 180))

    def test_one_hidden_leg_still_measures_the_other(self) -> None:
        sample = measure_pose(hide(standing_pose(), LEFT_ANKLE), ASPECT)
        self.assertIsNone(sample.left_knee_angle_degrees)
        self.assertAlmostEqual(sample.right_knee_angle_degrees or 0, 180, delta=0.1)

    def test_moving_or_scaling_the_body_does_not_change_the_knee_angle(self) -> None:
        bent = bend_both(standing_pose(), 15)
        original = measure_pose(bent, ASPECT).left_knee_angle_degrees or 0
        moved = measure_pose(shift(bent, x=0.15, y=-0.05), ASPECT).left_knee_angle_degrees or 0
        smaller = measure_pose(shift(bent, x=0.05, y=0.05, scale=0.5), ASPECT).left_knee_angle_degrees or 0
        self.assertAlmostEqual(original, 165, delta=0.2)
        self.assertAlmostEqual(original, moved, delta=0.1)
        self.assertAlmostEqual(original, smaller, delta=0.1)

    def test_hand_rise_is_relative_to_the_calibrated_height(self) -> None:
        self.assertAlmostEqual(hand_rise(-0.65, -1.40), 0.75)
        self.assertIsNone(hand_rise(-0.65, None))

    def test_clearer_leg_is_selected_and_a_close_side_does_not_steal_it(self) -> None:
        self.assertEqual(
            select_leg_side(0.55, 0.95, 170, 170, SIDE_NONE, 0.5, 0.15),
            SIDE_RIGHT,
        )
        self.assertEqual(
            select_leg_side(0.80, 0.90, 170, 170, SIDE_LEFT, 0.5, 0.15),
            SIDE_LEFT,
        )
        self.assertEqual(
            select_leg_side(0.55, 0.95, 170, 170, SIDE_LEFT, 0.5, 0.15),
            SIDE_RIGHT,
        )

    def test_neither_reliable_leg_selects_none(self) -> None:
        self.assertEqual(
            select_leg_side(0.2, 0.4, None, None, SIDE_LEFT, 0.5, 0.15),
            SIDE_NONE,
        )

    def test_vertical_leg_stays_neutral_when_the_frame_aspect_changes(self) -> None:
        session = PoseSession()
        pose = standing_pose()
        session.start_calibration(0.0)
        session.update(pose, 4 / 3, 2.5)
        view = session.update(pose, 4 / 3, 3.0)
        self.assertEqual(view.squat_state, STANDING)
        self.assertIsNotNone(view.crouch_degrees)
        self.assertAlmostEqual(view.crouch_degrees, 0.0, delta=0.1)


class HysteresisTests(unittest.TestCase):
    def test_enter_is_harder_than_exit(self) -> None:
        holding, state = latch_update(False, 0.19, 0.20, 0.12, SQUAT, STANDING)
        self.assertEqual((holding, state), (False, STANDING))

        holding, state = latch_update(False, 0.20, 0.20, 0.12, SQUAT, STANDING)
        self.assertEqual((holding, state), (True, SQUAT))

        holding, state = latch_update(True, 0.12, 0.20, 0.12, SQUAT, STANDING)
        self.assertEqual((holding, state), (True, SQUAT))

        holding, state = latch_update(True, 0.11, 0.20, 0.12, SQUAT, STANDING)
        self.assertEqual((holding, state), (False, STANDING))

    def test_missing_value_does_not_keep_the_old_state(self) -> None:
        holding, state = latch_update(True, None, 0.20, 0.12, SQUAT, STANDING)
        self.assertEqual((holding, state), (False, UNKNOWN))

    def test_exit_above_enter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PoseConfig(squat_enter=0.10, squat_exit=0.20)


class SquatTransitionTests(unittest.TestCase):
    def test_calibration_uses_only_the_last_second(self) -> None:
        session = PoseSession()
        neutral = standing_pose()
        early_bend = bend_both(neutral, 30)
        session.start_calibration(0.0)
        session.update(early_bend, ASPECT, 1.0)
        session.update(neutral, ASPECT, 2.5)
        view = session.update(neutral, ASPECT, 3.0)
        self.assertEqual(view.status, "tracking")
        self.assertAlmostEqual(view.calibrated_knee_angle or 0, 180, delta=0.1)
        self.assertEqual(view.squat_state, STANDING)
        self.assertIsNotNone(view.crouch_degrees)
        self.assertAlmostEqual(view.crouch_degrees, 0.0, delta=0.1)

    def test_one_visible_leg_detects_a_small_bend(self) -> None:
        session, neutral = calibrated_session()
        one_leg = set_visibility(bend_knee(neutral, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, 10), RIGHT_LEG, 0.1)
        view = session.update(one_leg, ASPECT, 4.0)
        self.assertEqual(view.squat_side, SIDE_LEFT)
        self.assertEqual(view.squat_state, SQUAT)
        self.assertAlmostEqual(view.crouch_degrees or 0, 10, delta=0.2)
        self.assertGreater(view.live_knee_angle or 0, 140)
        self.assertEqual(view.squat_note, "")

    def test_bend_below_enter_stays_standing(self) -> None:
        session, neutral = calibrated_session()
        view = session.update(bend_both(neutral, 8), ASPECT, 4.0)
        self.assertEqual(view.squat_state, STANDING)
        self.assertAlmostEqual(view.crouch_degrees or 0, 8, delta=0.2)

    def test_jitter_inside_the_band_does_not_toggle(self) -> None:
        session, neutral = calibrated_session()
        self.assertEqual(session.update(bend_both(neutral, 10), ASPECT, 4.0).squat_state, SQUAT)
        held = session.update(bend_both(neutral, 6), ASPECT, 4.2)
        self.assertEqual(held.squat_state, SQUAT)
        self.assertAlmostEqual(held.crouch_degrees or 0, 6, delta=0.2)
        released = session.update(bend_both(neutral, 4), ASPECT, 4.4)
        self.assertEqual(released.squat_state, STANDING)

    def test_no_reliable_leg_is_not_classified(self) -> None:
        session, neutral = calibrated_session()
        hidden = set_visibility(set_visibility(neutral, LEFT_LEG, 0.1), RIGHT_LEG, 0.2)
        view = session.update(hidden, ASPECT, 4.0)
        self.assertEqual(view.squat_side, SIDE_NONE)
        self.assertEqual(view.squat_state, UNKNOWN)
        self.assertIn("neither", view.squat_note)
        self.assertIsNone(view.crouch_degrees)

    def test_a_side_missing_from_calibration_is_not_used(self) -> None:
        session = PoseSession()
        left_only = set_visibility(standing_pose(), RIGHT_LEG, 0.1)
        session.start_calibration(0.0)
        session.update(left_only, ASPECT, 2.5)
        ready = session.update(left_only, ASPECT, 3.0)
        self.assertEqual(ready.squat_side, SIDE_LEFT)
        self.assertEqual(ready.squat_state, STANDING)

        right_only = set_visibility(bend_knee(standing_pose(), RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, 20), LEFT_LEG, 0.1)
        blocked = session.update(right_only, ASPECT, 4.0)
        self.assertEqual(blocked.squat_side, SIDE_RIGHT)
        self.assertEqual(blocked.squat_state, UNKNOWN)
        self.assertIn("RIGHT", blocked.squat_note)

        left_bent = set_visibility(bend_knee(standing_pose(), LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, 10), RIGHT_LEG, 0.1)
        detected = session.update(left_bent, ASPECT, 4.2)
        self.assertEqual(detected.squat_side, SIDE_LEFT)
        self.assertEqual(detected.squat_state, SQUAT)

    def test_straight_knees_do_not_count_as_a_squat(self) -> None:
        session, neutral = calibrated_session()
        view = session.update(with_hips(neutral, 0.70), ASPECT, 4.0)
        self.assertEqual(view.squat_state, STANDING)
        self.assertAlmostEqual(view.live_knee_angle or 0, 180, delta=1)

    def test_hidden_leg_must_cross_enter_again(self) -> None:
        session, neutral = calibrated_session()
        self.assertEqual(session.update(bend_both(neutral, 10), ASPECT, 4.0).squat_state, SQUAT)
        hidden = set_visibility(set_visibility(neutral, LEFT_LEG, 0.1), RIGHT_LEG, 0.1)
        lost = session.update(hidden, ASPECT, 4.2)
        self.assertEqual(lost.squat_side, SIDE_NONE)
        self.assertEqual(lost.squat_state, UNKNOWN)
        between = session.update(bend_both(neutral, 6), ASPECT, 4.4)
        self.assertEqual(between.squat_state, STANDING)
        self.assertEqual(session.update(bend_both(neutral, 10), ASPECT, 4.6).squat_state, SQUAT)

    def test_calibration_fails_when_no_leg_is_visible(self) -> None:
        session = PoseSession()
        hidden = set_visibility(set_visibility(standing_pose(), LEFT_LEG, 0.1), RIGHT_LEG, 0.1)
        session.start_calibration(0.0)
        session.update(hidden, ASPECT, 2.5)
        view = session.update(hidden, ASPECT, 3.0)
        self.assertIn("no reliable leg", view.status)
        self.assertEqual(view.squat_state, UNKNOWN)

    def test_image_angle_matches_a_constructed_bend(self) -> None:
        bent = bend_knee(standing_pose(), LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, 10)
        angle = joint_angle_degrees(bent[LEFT_HIP], bent[LEFT_KNEE], bent[LEFT_ANKLE], ASPECT)
        self.assertAlmostEqual(angle or 0, 170, delta=0.2)


class HandTransitionTests(unittest.TestCase):
    def test_left_raise_uses_the_calibrated_wrist_height(self) -> None:
        session, neutral = calibrated_session()
        raised = with_wrist(neutral, LEFT_WRIST, 0.43)
        view = session.update(raised, ASPECT, 4.0)
        self.assertEqual(view.left_hand_state, HAND_UP)
        self.assertEqual(view.right_hand_state, HAND_DOWN)
        self.assertEqual(view.hands_state, LEFT_HAND_UP)
        self.assertGreaterEqual(view.left_hand_rise or 0, 0.75)

    def test_hand_hysteresis_and_both_hands(self) -> None:
        session, neutral = calibrated_session()
        left_up = with_wrist(neutral, LEFT_WRIST, 0.43)
        held = with_wrist(left_up, LEFT_WRIST, 0.48)
        lowered = with_wrist(neutral, LEFT_WRIST, 0.52)
        self.assertEqual(session.update(left_up, ASPECT, 4.0).hands_state, LEFT_HAND_UP)
        self.assertEqual(session.update(held, ASPECT, 4.2).hands_state, LEFT_HAND_UP)
        self.assertEqual(session.update(lowered, ASPECT, 4.4).hands_state, HAND_DOWN)

        both = with_wrist(with_wrist(neutral, LEFT_WRIST, 0.43), RIGHT_WRIST, 0.43)
        view = session.update(both, ASPECT, 4.6)
        self.assertEqual(view.hands_state, BOTH_HANDS_UP)

    def test_right_hand_only(self) -> None:
        session, neutral = calibrated_session()
        view = session.update(with_wrist(neutral, RIGHT_WRIST, 0.43), ASPECT, 4.0)
        self.assertEqual(view.hands_state, RIGHT_HAND_UP)

    def test_hidden_wrist_is_not_classified(self) -> None:
        session, neutral = calibrated_session()
        view = session.update(hide(neutral, LEFT_WRIST), ASPECT, 4.0)
        self.assertEqual(view.left_hand_state, UNKNOWN)
        self.assertFalse(view.left_wrist_visible)
        self.assertEqual(view.right_hand_state, HAND_DOWN)

    def test_states_stay_unknown_until_calibration(self) -> None:
        session = PoseSession()
        view = session.update(with_hips(standing_pose(), 0.70), ASPECT, 0.0)
        self.assertEqual(view.status, "press C to calibrate")
        self.assertEqual(view.squat_state, UNKNOWN)
        self.assertEqual(view.hands_state, UNKNOWN)


if __name__ == "__main__":
    unittest.main()
