"""Classify one acceleration sample as LEFT, CENTER, or RIGHT.

Which MPU-6050 axis tracks skateboard lean is still unknown. Pick it with
MovementConfig.steering_axis after watching live X/Y/Z readings. A leading
minus, such as "-y", flips the sign if that axis moves the wrong way.

Thresholds are in the same units as MPU6050.get_acceleration() (g). The
defaults below are placeholders for the first physical test, not measured
skateboard angles.
"""

from __future__ import annotations

from dataclasses import dataclass

LEFT = "LEFT"
CENTER = "CENTER"
RIGHT = "RIGHT"

STEERING_AXES = ("x", "y", "z", "-x", "-y", "-z")


@dataclass(frozen=True)
class MovementConfig:
    """Settings to tune after leaning the mounted board.

    steering_axis: acceleration component to treat as lean. Not confirmed yet.
    center_offset: rider-neutral reading on that axis. Subtracted before
        classification so a resting board does not have to read 0 g.
    left_threshold: adjusted value at or below this is LEFT. Must be negative
        and outside the dead zone.
    right_threshold: adjusted value at or above this is RIGHT. Must be positive
        and outside the dead zone.
    dead_zone: half-width around 0 that stays CENTER.
    """

    steering_axis: str = "x"
    center_offset: float = 0.0
    left_threshold: float = -0.20
    right_threshold: float = 0.20
    dead_zone: float = 0.08

    def __post_init__(self) -> None:
        if self.steering_axis not in STEERING_AXES:
            raise ValueError(
                f"steering_axis must be one of {STEERING_AXES}, "
                f"got {self.steering_axis!r}."
            )
        if self.dead_zone < 0:
            raise ValueError("dead_zone must be zero or positive.")
        if self.left_threshold >= -self.dead_zone:
            raise ValueError(
                "left_threshold must be more negative than -dead_zone."
            )
        if self.right_threshold <= self.dead_zone:
            raise ValueError("right_threshold must be greater than dead_zone.")


def select_steering(acceleration: dict[str, float], config: MovementConfig) -> float:
    """Return the configured axis value, with a sign flip when requested."""
    axis = config.steering_axis
    sign = -1.0 if axis.startswith("-") else 1.0
    name = axis[-1]
    try:
        value = acceleration[name]
    except KeyError as exc:
        raise KeyError(
            f"Acceleration reading has no {name!r} axis. "
            f"Keys: {sorted(acceleration)}."
        ) from exc
    return sign * float(value)


def adjusted_steering(
    acceleration: dict[str, float],
    config: MovementConfig | None = None,
) -> float:
    """Steering value after the neutral center offset is removed."""
    config = config or MovementConfig()
    return select_steering(acceleration, config) - config.center_offset


def classify_steering(
    adjusted: float,
    config: MovementConfig | None = None,
) -> str:
    """Map an offset-adjusted steering value to LEFT, CENTER, or RIGHT.

    The dead zone is applied first. Values outside it but short of a threshold
    stay CENTER. A value exactly on a threshold counts as that side.
    """
    config = config or MovementConfig()
    if abs(adjusted) <= config.dead_zone:
        return CENTER
    if adjusted <= config.left_threshold:
        return LEFT
    if adjusted >= config.right_threshold:
        return RIGHT
    return CENTER


def classify_movement(
    acceleration: dict[str, float],
    config: MovementConfig | None = None,
) -> str:
    """Classify acceleration into LEFT, CENTER, or RIGHT.

    This does not read the sensor and does not generate keyboard input.
    """
    config = config or MovementConfig()
    return classify_steering(adjusted_steering(acceleration, config), config)


# --- Analog steering (virtual gamepad) --------------------------------------
# These work on filtered orientation angles in degrees (controller/orientation.py)
# rather than raw g, so a lean maps proportionally onto a stick.


def board_axis(orientation: dict[str, float], source: str, invert: bool, center: float = 0.0) -> float:
    """Pick one orientation channel ('roll' or 'pitch'), remove the neutral offset, apply sign."""
    value = orientation[source] - center
    return -value if invert else value


def angle_to_stick(angle: float, dead_zone: float, max_angle: float) -> float:
    """Map a lean angle to a stick value in [-1, 1].

    Inside the dead zone the stick rests at 0; outside it ramps linearly from the
    dead zone edge and saturates at max_angle.
    """
    magnitude = abs(angle)
    if magnitude <= dead_zone:
        return 0.0
    span = max(max_angle - dead_zone, 1e-6)
    value = min((magnitude - dead_zone) / span, 1.0)
    return value if angle > 0 else -value


def stick_state(stick: float) -> str:
    """LEFT / CENTER / RIGHT for a stick value (0 inside the dead zone)."""
    if stick > 0:
        return RIGHT
    if stick < 0:
        return LEFT
    return CENTER
