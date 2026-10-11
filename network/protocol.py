"""Encode and decode LEFT, CENTER, and RIGHT messages.

The Raspberry Pi sends one controller state per line. The laptop never
receives accelerometer readings.
"""

from __future__ import annotations

from controller.movement import CENTER, LEFT, RIGHT

VALID_STATES = (LEFT, CENTER, RIGHT)
DEFAULT_PORT = 5050


def encode_state(state: str) -> bytes:
    """Turn a controller state into one ASCII line."""
    if state not in VALID_STATES:
        raise ValueError(
            f"Controller state must be one of {VALID_STATES}, got {state!r}."
        )
    return f"{state}\n".encode("ascii")


def decode_state(line: str) -> str:
    """Return a controller state from one received line."""
    state = line.strip()
    if state not in VALID_STATES:
        raise ValueError(f"Unknown controller state: {line!r}.")
    return state


class StateDecoder:
    """Collect complete lines from a TCP byte stream."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, data: bytes) -> list[str]:
        self._buffer += data.decode("ascii")
        states: list[str] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip() == "":
                continue
            states.append(decode_state(line))
        return states
