"""Turn LEFT, CENTER, and RIGHT into keyboard input.

A one-letter binding is held until the state changes. A longer binding,
such as "hack", is typed once when that state begins and is not repeated
while the board stays there.
"""

from __future__ import annotations

from dataclasses import dataclass

from controller.movement import CENTER, LEFT, RIGHT


@dataclass(frozen=True)
class KeyBindings:
    """Text typed or held for the two steering directions.

    LEFT types hack. RIGHT types lanta_. Pass one letter, such as a and d,
    when a game should see a held key instead.
    """

    left: str = "hack"
    right: str = "lanta_"

    def __post_init__(self) -> None:
        left = _normalize_binding(self.left, "left")
        right = _normalize_binding(self.right, "right")
        if left == right:
            raise ValueError("LEFT and RIGHT must use different inputs.")
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)


class KeyboardOutput:
    """Track the held steering key and drive a keyboard controller."""

    def __init__(self, bindings: KeyBindings | None = None, keyboard=None) -> None:
        self.bindings = bindings or KeyBindings()
        self._keyboard = keyboard if keyboard is not None else pynput_keyboard()
        self._active: str | None = None
        self._held_key: str | None = None

    def apply_state(self, state: str) -> bool:
        """Apply this state once. Return True when the active input changes."""
        desired = self._key_for(state)
        if desired == self._active:
            return False
        if desired is None:
            self.close()
            return True
        self._release_held_key()
        self._active = desired
        if _is_single_letter(desired):
            self._held_key = desired
            self._keyboard.press(desired)
        else:
            self._keyboard.type(desired)
        return True

    def close(self) -> None:
        """Release any held steering key. Safe to call more than once."""
        released: list[str] = []
        if self._held_key is not None:
            self._keyboard.release(self._held_key)
            released.append(self._held_key)
            self._held_key = None
        for key in (self.bindings.left, self.bindings.right):
            if not _is_single_letter(key) or key in released:
                continue
            self._keyboard.release(key)
            released.append(key)
        self._active = None

    def status_line(self) -> str:
        if self._active == self.bindings.left:
            return f"LEFT  {_action_word(self.bindings.left)} {self.bindings.left}"
        if self._active == self.bindings.right:
            return f"RIGHT  {_action_word(self.bindings.right)} {self.bindings.right}"
        return "CENTER  keys released"

    def _release_held_key(self) -> None:
        if self._held_key is None:
            return
        self._keyboard.release(self._held_key)
        self._held_key = None

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

    def type(self, text: str) -> None:
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


def _normalize_binding(value: str, name: str) -> str:
    if not value or any(not (character.isalnum() or character == "_") for character in value):
        raise ValueError(
            f"{name} input must be letters, digits, or underscore, got {value!r}."
        )
    if _is_single_letter(value):
        return value.lower()
    return value


def _is_single_letter(value: str) -> bool:
    return len(value) == 1 and value.isalpha()


def _action_word(value: str) -> str:
    if _is_single_letter(value):
        return "holding"
    return "typed"
