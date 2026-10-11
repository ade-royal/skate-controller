"""Calibration helpers for inertial sensor readings."""


def apply_offsets(reading, offsets=None):
    """Apply axis offsets to a reading dictionary."""
    offsets = offsets or {}
    return {axis: value - offsets.get(axis, 0) for axis, value in reading.items()}
