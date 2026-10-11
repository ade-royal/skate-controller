"""Calibration helpers for inertial sensor readings."""

from __future__ import annotations


def apply_offsets(reading, offsets=None):
    """Apply axis offsets to a reading dictionary."""
    offsets = offsets or {}
    return {axis: value - offsets.get(axis, 0) for axis, value in reading.items()}


def gyro_bias(samples: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Mean gyro reading while the board is held still; subtract it from later readings."""
    if not samples:
        return 0.0, 0.0, 0.0
    n = len(samples)
    return (
        sum(s[0] for s in samples) / n,
        sum(s[1] for s in samples) / n,
        sum(s[2] for s in samples) / n,
    )
