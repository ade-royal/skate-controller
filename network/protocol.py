"""Encode and decode steering states and ollie events.

The Raspberry Pi sends one steering state per line: LEFT, CENTER, or RIGHT.
An ollie is an extra OLLIE line in the same send, so a lean is not replaced.
The laptop never receives accelerometer readings.
"""

from __future__ import annotations

from controller.movement import CENTER, LEFT, RIGHT
from controller.ollie import OLLIE

STEERING_STATES = (LEFT, CENTER, RIGHT)
VALID_STATES = (LEFT, CENTER, RIGHT, OLLIE)
DEFAULT_PORT = 5050


def encode_state(state: str) -> bytes:
    """Turn one steering state or ollie event into an ASCII line."""
    if state not in VALID_STATES:
        raise ValueError(
            f"Controller state must be one of {VALID_STATES}, got {state!r}."
        )
    return f"{state}\n".encode("ascii")


def encode_update(steering: str, event: str | None = None) -> bytes:
    """Encode the steering line, plus an OLLIE line when an event fired."""
    if steering not in STEERING_STATES:
        raise ValueError(
            f"Steering state must be one of {STEERING_STATES}, got {steering!r}."
        )
    payload = encode_state(steering)
    if event is None:
        return payload
    if event != OLLIE:
        raise ValueError(f"Ollie event must be {OLLIE!r}, got {event!r}.")
    return payload + encode_state(event)


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
