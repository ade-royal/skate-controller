"""Board-motion -> controller mapping config, persisted as JSON."""

from __future__ import annotations

import copy
import json
from pathlib import Path

# Which sensor axis is "lean" vs "nose" depends on how the IMU is mounted;
# pick them on the dashboard by watching which one moves.
DEFAULT_CONFIG = {
    "lean": {"source": "roll", "invert": False},
    "nose": {"source": "pitch", "invert": False},
    "left_stick_x": {"deadzone_deg": 3.0, "max_deg": 15.0},
}

VALID_SOURCES = ("roll", "pitch")


def load_config(path: Path) -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path.exists():
        saved = json.loads(path.read_text())
        for key, value in saved.items():
            if key in config and isinstance(value, dict):
                config[key].update(value)
    return config


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2))


def merge_update(config: dict, update: dict) -> dict:
    """Apply a partial update from the dashboard, ignoring unknown keys and bad sources."""
    for key, value in update.items():
        if key not in config or not isinstance(value, dict):
            continue
        for field, field_value in value.items():
            if field not in config[key]:
                continue
            if field == "source" and field_value not in VALID_SOURCES:
                continue
            config[key][field] = type(config[key][field])(field_value)
    return config
