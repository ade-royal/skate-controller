"""Press and release steering keys from LEFT, CENTER, and RIGHT.

The laptop holds at most one steering key. A new direction releases the
previous key before the next press. Repeating the same state does not
press the key again.
"""

from __future__ import annotations

from dataclasses import dataclass

from controller.movement import CENTER, LEFT, RIGHT


@dataclass(frozen=True)
class KeyBindings:
    """Character keys for the two steering directions.

    Defaults match the first playable mapping: LEFT holds a, RIGHT holds d.
    """

    left: str = "a"
    right: str = "d"

    def __post_init__(self) -> None:
        left = _one_letter(self.left, "left")
        right = _one_letter(self.right, "right")
        if left == right:
            raise ValueError("LEFT and RIGHT must use different keys.")
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)


class KeyboardOutput:
    """Track the held steering key and drive a keyboard controller."""

    def __init__(self, bindings: KeyBindings | None = None, keyboard=None) -> None:
        self.bindings = bindings or KeyBindings()
        self._keyboard = keyboard if keyboard is not None else pynput_keyboard()
        self._held: str | None = None

    def apply_state(self, state: str) -> bool:
        """Hold the key for this state. Return True when the held key changes."""
        desired = self._key_for(state)
        if desired == self._held:
            return False
        if desired is None:
            self.close()
            return True
        if self._held is not None:
            key = self._held
            self._keyboard.release(key)
            self._held = None
        self._held = desired
        self._keyboard.press(desired)
        return True

    def close(self) -> None:
        """Release every steering key. Safe to call more than once."""
        released: list[str] = []
        for key in (self._held, self.bindings.left, self.bindings.right):
            if key is None or key in released:
                continue
            self._keyboard.release(key)
            released.append(key)
        self._held = None

    def status_line(self) -> str:
        if self._held == self.bindings.left:
            return f"LEFT  holding {self.bindings.left}"
        if self._held == self.bindings.right:
            return f"RIGHT  holding {self.bindings.right}"
        return "CENTER  keys released"

    def _key_for(self, state: str) -> str | None:
        if state == LEFT:
            return self.bindings.left
        if state == RIGHT:
            return self.bindings.right
        if state == CENTER:
            return None
        raise ValueError(
            f"Controller state must be {LEFT}, {CENTER}, or {RIGHT}, got {state!r}."
        )


class NullKeyboard:
    """Keyboard stand-in that does not press real keys."""

    def press(self, key: str) -> None:
        return None

    def release(self, key: str) -> None:
        return None


def pynput_keyboard():
    """Return a pynput controller. Import pynput only when keys are real."""
    try:
        from pynput.keyboard import Controller
    except ImportError as exc:
        raise ImportError(
            "pynput is required for keyboard output. "
            "On the Windows laptop run: pip install pynput"
        ) from exc
    return Controller()


def _one_letter(key: str, name: str) -> str:
    if len(key) != 1 or not key.isalpha():
        raise ValueError(f"{name} key must be one letter, got {key!r}.")
    return key.lower()
