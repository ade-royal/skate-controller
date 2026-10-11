"""Recognize the recorded back-foot dip/rebound without producing game input."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PopConfig:
    negative_dps: float = -50.0
    positive_dps: float = 40.0
    reversal_window_s: float = 0.9
    cooldown_s: float = 1.0
    max_gap_s: float = 0.25


class PopDetector:
    """Same causal rule as the standalone live preview, using monotonic time."""

    def __init__(self, config: PopConfig | None = None) -> None:
        self.config = config or PopConfig()
        self.reset()

    def reset(self) -> None:
        self.armed_at: float | None = None
        self.last_sample: float | None = None
        self.cooldown_until = float("-inf")

    def update(self, now: float, gyro_y: float) -> bool:
        if not math.isfinite(now) or not math.isfinite(gyro_y):
            self.reset()
            return False
        cfg = self.config
        if self.last_sample is not None and (
            now < self.last_sample or now - self.last_sample > cfg.max_gap_s
        ):
            self.armed_at = None
        self.last_sample = now
        if now < self.cooldown_until:
            return False
        if self.armed_at is not None and now - self.armed_at > cfg.reversal_window_s:
            self.armed_at = None
        if self.armed_at is None and gyro_y <= cfg.negative_dps:
            self.armed_at = now
        elif self.armed_at is not None and gyro_y >= cfg.positive_dps:
            self.armed_at = None
            self.cooldown_until = now + cfg.cooldown_s
            return True
        return False
