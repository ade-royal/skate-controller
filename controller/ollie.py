"""Detect one ollie event from accelerometer X.

Mounted-board testing treated a pop as accel X at or above 0.300 g.
This is a separate event from Y-axis LEFT / CENTER / RIGHT. The cooldown
is a starting gap so one pop cannot fire again on the next samples. It is
not a measured time between tricks.
"""

from __future__ import annotations

from dataclasses import dataclass

OLLIE = "OLLIE"


@dataclass(frozen=True)
class OllieConfig:
    """Ollie settings. threshold is in g, the same units as get_acceleration()."""

    threshold: float = 0.300
    cooldown: float = 0.40

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise ValueError("ollie threshold must be positive.")
        if self.cooldown < 0:
            raise ValueError("ollie cooldown must be zero or positive.")


class OllieDetector:
    """Fire once when accel X crosses the threshold, then wait to re-arm.

    Re-arm requires the reading to fall back below the threshold. A second
    crossing inside the cooldown is ignored, including if X is still high
    when the cooldown ends.
    """

    def __init__(self, config: OllieConfig | None = None) -> None:
        self.config = config or OllieConfig()
        self._above = False
        self._ready_at = 0.0

    def update(self, accel_x: float, now: float) -> str | None:
        """Return OLLIE on a new crossing, or None."""
        above = float(accel_x) >= self.config.threshold
        if not above:
            self._above = False
            return None
        if self._above or now < self._ready_at:
            self._above = True
            return None
        self._above = True
        self._ready_at = now + self.config.cooldown
        return OLLIE

    def arm_status(self, now: float, above: bool) -> str:
        """Cooldown and re-arm text for the debug panel. Does not detect."""
        remaining = self._ready_at - now
        if above and self._above and remaining > 0:
            return f"cooldown {remaining:.2f}s"
        if above and self._above:
            return f"above gate, drop below {self.config.threshold:.3f} to re-arm"
        if remaining > 0:
            return f"below gate, cooldown {remaining:.2f}s"
        return "armed"
