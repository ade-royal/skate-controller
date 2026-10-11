"""Classify one acceleration sample as LEFT, CENTER, or RIGHT.

Mounted-board testing showed accelerometer Y tracks lean. Negative Y is
left and positive Y is right. A leading minus on steering_axis, such as
"-y", flips that sign if a later test shows the opposite.

Thresholds are in g, the same units as MPU6050.get_acceleration(), after
center_offset is subtracted. The defaults come from one approximate pass:

    neutral Y          +0.008 g -> adjusted  0.000 g
    normal left        -0.045 g -> adjusted -0.053 g
    normal right       +0.045 g -> adjusted +0.037 g
    extreme left       -0.075 g -> adjusted -0.083 g
    extreme right      +0.075 g -> adjusted +0.067 g

left_threshold and right_threshold are those normal leans. They are the
initial turn points, not a final tuning. The dead zone is half of the
shorter normal lean (0.037 / 2 = 0.018 g). No separate wobble measurement
was taken, so that inner band is a starting width around neutral.
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

    steering_axis: acceleration component to treat as lean. "y" matches the
        mounted board: negative is left, positive is right.
    center_offset: rider-neutral reading on that axis. Subtracted before
        classification. 0.008 g is the measured resting Y.
    left_threshold: adjusted value at or below this is LEFT. Must be negative
        and outside the dead zone. -0.053 g is the measured normal left lean.
    right_threshold: adjusted value at or above this is RIGHT. Must be positive
        and outside the dead zone. 0.037 g is the measured normal right lean.
    dead_zone: half-width around 0 that stays CENTER. 0.018 g is half of the
        shorter normal lean and has not been measured as sensor noise.
    """

    steering_axis: str = "y"
    center_offset: float = 0.008
    left_threshold: float = -0.053
    right_threshold: float = 0.037
    dead_zone: float = 0.018

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
