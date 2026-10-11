"""Calibrated squat and hand-raise measurements.

Squat uses one leg at a time because the laptop camera sees the rider from
the side. The crouch is extra knee bend past the user's own neutral stance,
not a deep squat and not a fixed screen position. This module does not open
a webcam and does not press keys.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# MediaPipe Pose Landmarker indices. Image y grows downward.
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

LANDMARK_COUNT = 33

SQUAT = "SQUAT"
STANDING = "STANDING"
HAND_UP = "HAND_UP"
HAND_DOWN = "HAND_DOWN"
BOTH_HANDS_UP = "BOTH_HANDS_UP"
LEFT_HAND_UP = "LEFT_HAND_UP"
RIGHT_HAND_UP = "RIGHT_HAND_UP"
UNKNOWN = "UNKNOWN"
SIDE_LEFT = "LEFT"
SIDE_RIGHT = "RIGHT"
SIDE_NONE = "NONE"

POSE_CONNECTIONS = (
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_SHOULDER, LEFT_ELBOW),
    (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW),
    (RIGHT_ELBOW, RIGHT_WRIST),
    (LEFT_SHOULDER, LEFT_HIP),
    (RIGHT_SHOULDER, RIGHT_HIP),
    (LEFT_HIP, RIGHT_HIP),
    (LEFT_HIP, LEFT_KNEE),
    (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE),
    (RIGHT_KNEE, RIGHT_ANKLE),
)


@dataclass(frozen=True)
class Landmark:
    """One pose point. x and y are normalized image coordinates."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


@dataclass(frozen=True)
class PoseConfig:
    """Thresholds to tune from the webcam debug view.

    Squat enter/exit are degrees of extra knee bend past the calibrated
    stance. 10 and 5 are a sensitive starting pair for a small riding crouch.
    They are not a measured final calibration. Hand enter/exit are how far a
    wrist must rise above its calibrated height, in current shoulder-widths.
    """

    visibility_min: float = 0.5
    calibration_seconds: float = 3.0
    calibration_average_seconds: float = 1.0
    squat_enter: float = 10.0
    squat_exit: float = 5.0
    side_switch_margin: float = 0.15
    hand_enter: float = 0.75
    hand_exit: float = 0.45

    def __post_init__(self) -> None:
        if not 0 <= self.visibility_min <= 1:
            raise ValueError("visibility_min must be from 0 to 1.")
        if self.calibration_seconds <= 0 or self.calibration_average_seconds <= 0:
            raise ValueError("calibration times must be positive.")
        if self.calibration_average_seconds > self.calibration_seconds:
            raise ValueError("calibration average window cannot be longer than calibration.")
        if self.side_switch_margin < 0:
            raise ValueError("side_switch_margin cannot be negative.")
        _check_band("squat", self.squat_enter, self.squat_exit)
        _check_band("hand", self.hand_enter, self.hand_exit)


@dataclass(frozen=True)
class PoseSample:
    """Body-scaled measurements from one frame. None means not visible."""

    shoulder_width: float | None
    torso_length: float | None
    left_hand: float | None
    right_hand: float | None
    left_knee_angle_degrees: float | None
    right_knee_angle_degrees: float | None
    left_leg_visibility: float
    right_leg_visibility: float
    left_hip_visibility: float
    left_knee_visibility: float
    left_ankle_visibility: float
    right_hip_visibility: float
    right_knee_visibility: float
    right_ankle_visibility: float
    shoulders_visible: bool
    hips_visible: bool
    left_wrist_visible: bool
    right_wrist_visible: bool


@dataclass(frozen=True)
class PoseBaseline:
    """Averages from the last second of a neutral calibration."""

    left_knee_angle: float | None
    right_knee_angle: float | None
    left_hand: float | None
    right_hand: float | None
    shoulder_width: float | None
    torso_length: float | None


@dataclass(frozen=True)
class PoseView:
    """Everything the debug window needs for one frame."""

    status: str
    calibration_remaining: float | None
    squat_side: str
    squat_note: str
    squat_state: str
    crouch_degrees: float | None
    live_knee_angle: float | None
    calibrated_knee_angle: float | None
    left_knee_angle_degrees: float | None
    right_knee_angle_degrees: float | None
    left_leg_visibility: float
    right_leg_visibility: float
    left_hip_visibility: float
    left_knee_visibility: float
    left_ankle_visibility: float
    right_hip_visibility: float
    right_knee_visibility: float
    right_ankle_visibility: float
    hands_state: str
    left_hand_state: str
    right_hand_state: str
    left_hand_level: float | None
    right_hand_level: float | None
    left_hand_rise: float | None
    right_hand_rise: float | None
    shoulder_width: float | None
    torso_length: float | None
    shoulders_visible: bool
    hips_visible: bool
    left_wrist_visible: bool
    right_wrist_visible: bool


def measure_pose(
    landmarks: list[Landmark] | None,
    aspect: float,
    config: PoseConfig | None = None,
) -> PoseSample:
    """Measure one pose. aspect is image width divided by image height."""
    config = config or PoseConfig()
    if landmarks is None or len(landmarks) < LANDMARK_COUNT or aspect <= 0:
        return _empty_sample()

    shoulders_visible = _visible(
        landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER], minimum=config.visibility_min
    )
    hips_visible = _visible(
        landmarks[LEFT_HIP], landmarks[RIGHT_HIP], minimum=config.visibility_min
    )
    left_wrist_visible = _visible(landmarks[LEFT_WRIST], minimum=config.visibility_min)
    right_wrist_visible = _visible(landmarks[RIGHT_WRIST], minimum=config.visibility_min)

    shoulder_width = None
    torso_length = None
    if shoulders_visible and hips_visible:
        shoulder_width = abs(landmarks[LEFT_SHOULDER].x - landmarks[RIGHT_SHOULDER].x) * aspect
        torso_length = _torso_length(landmarks, aspect)
        if shoulder_width <= 0:
            shoulder_width = None
        if torso_length <= 0:
            torso_length = None

    left_hip, left_knee, left_ankle = _leg_visibility(landmarks, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE)
    right_hip, right_knee, right_ankle = _leg_visibility(landmarks, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE)
    return PoseSample(
        shoulder_width=shoulder_width,
        torso_length=torso_length,
        left_hand=_hand_height(
            landmarks, LEFT_SHOULDER, LEFT_WRIST, shoulder_width, left_wrist_visible
        ),
        right_hand=_hand_height(
            landmarks, RIGHT_SHOULDER, RIGHT_WRIST, shoulder_width, right_wrist_visible
        ),
        left_knee_angle_degrees=_knee_angle(
            landmarks, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, aspect, config
        ),
        right_knee_angle_degrees=_knee_angle(
            landmarks, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, aspect, config
        ),
        left_leg_visibility=min(left_hip, left_knee, left_ankle),
        right_leg_visibility=min(right_hip, right_knee, right_ankle),
        left_hip_visibility=left_hip,
        left_knee_visibility=left_knee,
        left_ankle_visibility=left_ankle,
        right_hip_visibility=right_hip,
        right_knee_visibility=right_knee,
        right_ankle_visibility=right_ankle,
        shoulders_visible=shoulders_visible,
        hips_visible=hips_visible,
        left_wrist_visible=left_wrist_visible and shoulders_visible,
        right_wrist_visible=right_wrist_visible and shoulders_visible,
    )


def knee_crouch_degrees(current_angle: float | None, neutral_angle: float | None) -> float | None:
    """Extra knee bend, in degrees, relative to the calibrated stance.

    A straight leg is near 180. Bending the knee makes the angle smaller, so
    a positive result means a deeper crouch than the user's neutral posture.
    """
    if current_angle is None or neutral_angle is None:
        return None
    # Hundredths of a degree. This keeps an exact threshold from missing
    # because 180 - 170 is 9.999999999999972 in floating point.
    return round(neutral_angle - current_angle, 2)


def select_leg_side(
    left_score: float,
    right_score: float,
    left_angle: float | None,
    right_angle: float | None,
    previous: str,
    minimum: float,
    switch_margin: float,
) -> str:
    """Pick the clearer leg. Neither side is required to be visible."""
    left_ok = left_angle is not None and left_score >= minimum
    right_ok = right_angle is not None and right_score >= minimum
    if left_ok and right_ok:
        if previous == SIDE_LEFT and left_score + switch_margin >= right_score:
            return SIDE_LEFT
        if previous == SIDE_RIGHT and right_score + switch_margin >= left_score:
            return SIDE_RIGHT
        if left_score >= right_score:
            return SIDE_LEFT
        return SIDE_RIGHT
    if left_ok:
        return SIDE_LEFT
    if right_ok:
        return SIDE_RIGHT
    return SIDE_NONE


def hand_rise(current: float | None, neutral: float | None) -> float | None:
    """How far a wrist has risen above its calibrated height, in shoulder-widths."""
    if current is None or neutral is None:
        return None
    return current - neutral


def latch_update(
    holding: bool,
    value: float | None,
    enter: float,
    exit_: float,
    active: str,
    inactive: str,
) -> tuple[bool, str]:
    """Apply an enter/exit band. A missing value does not keep the old state."""
    if value is None:
        return False, UNKNOWN
    engaged = value >= (exit_ if holding else enter)
    return engaged, active if engaged else inactive


def average_baseline(samples: list[PoseSample]) -> PoseBaseline | None:
    """Average the fields that were visible. Return None when nothing was usable."""
    if not samples:
        return None
    left_knee = _mean(
        [sample.left_knee_angle_degrees for sample in samples if sample.left_knee_angle_degrees is not None]
    )
    right_knee = _mean(
        [sample.right_knee_angle_degrees for sample in samples if sample.right_knee_angle_degrees is not None]
    )
    if left_knee is None and right_knee is None:
        return None
    return PoseBaseline(
        left_knee_angle=left_knee,
        right_knee_angle=right_knee,
        left_hand=_mean([sample.left_hand for sample in samples if sample.left_hand is not None]),
        right_hand=_mean([sample.right_hand for sample in samples if sample.right_hand is not None]),
        shoulder_width=_mean(
            [sample.shoulder_width for sample in samples if sample.shoulder_width is not None]
        ),
        torso_length=_mean(
            [sample.torso_length for sample in samples if sample.torso_length is not None]
        ),
    )


def joint_angle_degrees(a: Landmark, b: Landmark, c: Landmark, aspect: float) -> float | None:
    """Return the image-plane angle at b, in degrees.

    x is multiplied by aspect so a wide frame does not stretch the bend.
    Depth is left out on purpose: the camera looks at the rider from the side,
    and monocular depth noise is large next to a small knee bend.
    """
    ba = ((a.x - b.x) * aspect, a.y - b.y)
    bc = ((c.x - b.x) * aspect, c.y - b.y)
    ba_length = math.hypot(*ba)
    bc_length = math.hypot(*bc)
    if ba_length == 0 or bc_length == 0:
        return None
    cosine = (ba[0] * bc[0] + ba[1] * bc[1]) / (ba_length * bc_length)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


class PoseSession:
    """Calibration countdown plus squat and hand latches."""

    def __init__(self, config: PoseConfig | None = None) -> None:
        self.config = config or PoseConfig()
        self.baseline: PoseBaseline | None = None
        self._calib_end: float | None = None
        self._samples: list[PoseSample] = []
        self._squat_holding = False
        self._squat_side = SIDE_NONE
        self._left_holding = False
        self._right_holding = False

    def start_calibration(self, now: float) -> None:
        """Begin a neutral-stance countdown. The previous baseline is cleared."""
        self._calib_end = now + self.config.calibration_seconds
        self._samples = []
        self.baseline = None
        self._squat_holding = False
        self._squat_side = SIDE_NONE
        self._left_holding = False
        self._right_holding = False

    def update(self, landmarks: list[Landmark] | None, aspect: float, now: float) -> PoseView:
        sample = measure_pose(landmarks, aspect, self.config)
        status, remaining = self._advance_calibration(sample, now)
        if landmarks is None:
            status = "no person"

        side = select_leg_side(
            sample.left_leg_visibility,
            sample.right_leg_visibility,
            sample.left_knee_angle_degrees,
            sample.right_knee_angle_degrees,
            self._squat_side,
            self.config.visibility_min,
            self.config.side_switch_margin,
        )
        self._squat_side = side
        live_angle, neutral_angle, crouch, note = _crouch_for_side(sample, self.baseline, side)

        left_rise = None
        right_rise = None
        if self.baseline is not None:
            left_rise = hand_rise(sample.left_hand, self.baseline.left_hand)
            right_rise = hand_rise(sample.right_hand, self.baseline.right_hand)

        self._squat_holding, squat_state = latch_update(
            self._squat_holding,
            crouch,
            self.config.squat_enter,
            self.config.squat_exit,
            SQUAT,
            STANDING,
        )
        self._left_holding, left_state = latch_update(
            self._left_holding,
            left_rise,
            self.config.hand_enter,
            self.config.hand_exit,
            HAND_UP,
            HAND_DOWN,
        )
        self._right_holding, right_state = latch_update(
            self._right_holding,
            right_rise,
            self.config.hand_enter,
            self.config.hand_exit,
            HAND_UP,
            HAND_DOWN,
        )
        if self.baseline is None and squat_state != UNKNOWN:
            squat_state = UNKNOWN
            self._squat_holding = False
        if self.baseline is None:
            left_state = UNKNOWN
            right_state = UNKNOWN
            self._left_holding = False
            self._right_holding = False

        return PoseView(
            status=status,
            calibration_remaining=remaining,
            squat_side=side,
            squat_note=note,
            squat_state=squat_state,
            crouch_degrees=crouch,
            live_knee_angle=live_angle,
            calibrated_knee_angle=neutral_angle,
            left_knee_angle_degrees=sample.left_knee_angle_degrees,
            right_knee_angle_degrees=sample.right_knee_angle_degrees,
            left_leg_visibility=sample.left_leg_visibility,
            right_leg_visibility=sample.right_leg_visibility,
            left_hip_visibility=sample.left_hip_visibility,
            left_knee_visibility=sample.left_knee_visibility,
            left_ankle_visibility=sample.left_ankle_visibility,
            right_hip_visibility=sample.right_hip_visibility,
            right_knee_visibility=sample.right_knee_visibility,
            right_ankle_visibility=sample.right_ankle_visibility,
            hands_state=_summarize_hands(left_state, right_state),
            left_hand_state=left_state,
            right_hand_state=right_state,
            left_hand_level=sample.left_hand,
            right_hand_level=sample.right_hand,
            left_hand_rise=left_rise,
            right_hand_rise=right_rise,
            shoulder_width=sample.shoulder_width,
            torso_length=sample.torso_length,
            shoulders_visible=sample.shoulders_visible,
            hips_visible=sample.hips_visible,
            left_wrist_visible=sample.left_wrist_visible,
            right_wrist_visible=sample.right_wrist_visible,
        )

    def _advance_calibration(self, sample: PoseSample, now: float) -> tuple[str, float | None]:
        if self._calib_end is None:
            if self.baseline is None:
                return "press C to calibrate", None
            return "tracking", None
        remaining = self._calib_end - now
        if now < self._calib_end:
            window_start = self._calib_end - self.config.calibration_average_seconds
            if _has_leg_angle(sample) and now >= window_start:
                self._samples.append(sample)
            return f"hold still {max(remaining, 0):.1f}s", remaining
        self.baseline = average_baseline(self._samples)
        self._samples = []
        self._calib_end = None
        if self.baseline is None:
            return "calibration failed: no reliable leg, press C", None
        return "tracking", None


def _hand_height(
    landmarks: list[Landmark],
    shoulder_index: int,
    wrist_index: int,
    shoulder_width: float | None,
    wrist_visible: bool,
) -> float | None:
    if not wrist_visible or shoulder_width is None or shoulder_width <= 0:
        return None
    # Positive when the wrist is above its shoulder. Image y grows downward.
    return (landmarks[shoulder_index].y - landmarks[wrist_index].y) / shoulder_width


def _knee_angle(
    landmarks: list[Landmark],
    hip_index: int,
    knee_index: int,
    ankle_index: int,
    aspect: float,
    config: PoseConfig,
) -> float | None:
    hip = landmarks[hip_index]
    knee = landmarks[knee_index]
    ankle = landmarks[ankle_index]
    if not _visible(hip, knee, ankle, minimum=config.visibility_min):
        return None
    return joint_angle_degrees(hip, knee, ankle, aspect)


def _leg_visibility(
    landmarks: list[Landmark], hip_index: int, knee_index: int, ankle_index: int
) -> tuple[float, float, float]:
    return (
        landmarks[hip_index].visibility,
        landmarks[knee_index].visibility,
        landmarks[ankle_index].visibility,
    )


def _crouch_for_side(
    sample: PoseSample, baseline: PoseBaseline | None, side: str
) -> tuple[float | None, float | None, float | None, str]:
    """Return live angle, calibrated angle, crouch degrees, and a short note."""
    if side == SIDE_NONE:
        return None, None, None, "neither hip/knee/ankle is reliable"
    live = sample.left_knee_angle_degrees if side == SIDE_LEFT else sample.right_knee_angle_degrees
    if baseline is None:
        return live, None, None, ""
    neutral = baseline.left_knee_angle if side == SIDE_LEFT else baseline.right_knee_angle
    if neutral is None:
        return live, None, None, f"{side} was not visible during calibration"
    return live, neutral, knee_crouch_degrees(live, neutral), ""


def _has_leg_angle(sample: PoseSample) -> bool:
    return sample.left_knee_angle_degrees is not None or sample.right_knee_angle_degrees is not None


def _torso_length(landmarks: list[Landmark], aspect: float) -> float:
    shoulder_x = (landmarks[LEFT_SHOULDER].x + landmarks[RIGHT_SHOULDER].x) / 2 * aspect
    hip_x = (landmarks[LEFT_HIP].x + landmarks[RIGHT_HIP].x) / 2 * aspect
    shoulder_y = (landmarks[LEFT_SHOULDER].y + landmarks[RIGHT_SHOULDER].y) / 2
    hip_y = (landmarks[LEFT_HIP].y + landmarks[RIGHT_HIP].y) / 2
    return math.hypot(shoulder_x - hip_x, shoulder_y - hip_y)


def _summarize_hands(left_state: str, right_state: str) -> str:
    left_up = left_state == HAND_UP
    right_up = right_state == HAND_UP
    if left_up and right_up:
        return BOTH_HANDS_UP
    if left_up:
        return LEFT_HAND_UP
    if right_up:
        return RIGHT_HAND_UP
    if left_state == UNKNOWN and right_state == UNKNOWN:
        return UNKNOWN
    return HAND_DOWN


def _empty_sample() -> PoseSample:
    return PoseSample(
        shoulder_width=None,
        torso_length=None,
        left_hand=None,
        right_hand=None,
        left_knee_angle_degrees=None,
        right_knee_angle_degrees=None,
        left_leg_visibility=0.0,
        right_leg_visibility=0.0,
        left_hip_visibility=0.0,
        left_knee_visibility=0.0,
        left_ankle_visibility=0.0,
        right_hip_visibility=0.0,
        right_knee_visibility=0.0,
        right_ankle_visibility=0.0,
        shoulders_visible=False,
        hips_visible=False,
        left_wrist_visible=False,
        right_wrist_visible=False,
    )


def _visible(*landmarks: Landmark, minimum: float) -> bool:
    return all(landmark.visibility >= minimum for landmark in landmarks)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _check_band(name: str, enter: float, exit_: float) -> None:
    if enter <= 0 or exit_ < 0 or exit_ > enter:
        raise ValueError(f"{name} exit must be from 0 through the enter threshold.")
