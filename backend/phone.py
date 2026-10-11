"""Phone remote: two buttons on an iPhone, served by the backend at /phone.

    Y   switches walk <-> skate mode in skate. (taps Y -> Xbox Y via the bridge)
    GO  toggle: walk mode holds W (left stick up), skate mode taps Left Shift
        (Xbox A, push) every PUSH_INTERVAL_S.

The game's mode can't be read, so it is tracked by counting Y presses
(starting in walk mode); the phone can correct it if it drifts.
"""

from __future__ import annotations

import asyncio
import time

Y_KEY = "y"  # tools/keyboard_pad.py: Y -> Xbox Y
WALK_KEY = "w"  # tools/keyboard_pad.py: W -> left stick up
TAP_S = 0.08
PUSH_INTERVAL_S = 0.6  # one push per interval while GO is on in skate mode
FLASH_S = 0.4
MODES = ("walk", "skate")


def _push_key():
    from pynput.keyboard import Key

    return Key.shift_l  # tools/keyboard_pad.py: Left Shift -> Xbox A


class PhoneRemote:
    def __init__(self, keyboard=None, push_key=None) -> None:
        if keyboard is None:
            from pynput.keyboard import Controller

            keyboard = Controller()
        self._kb = keyboard
        self._push_key = push_key if push_key is not None else _push_key()
        self.mode = "walk"
        self.go = False
        self.clients = 0
        self._walk_held = False
        self._push_task: asyncio.Task | None = None
        self._y_flash_until = 0.0

    # --- buttons --------------------------------------------------------
    async def press_y(self) -> None:
        """Switch walk <-> skate. Stops GO first so you don't roll off on switch."""
        self.set_go(False)
        self._kb.press(Y_KEY)
        await asyncio.sleep(TAP_S)
        self._kb.release(Y_KEY)
        self.mode = "skate" if self.mode == "walk" else "walk"
        self._y_flash_until = time.monotonic() + FLASH_S

    def set_go(self, on: bool) -> None:
        self._release_all()
        self.go = on
        if not on:
            return
        if self.mode == "walk":
            self._kb.press(WALK_KEY)
            self._walk_held = True
        else:
            self._push_task = asyncio.create_task(self._push_loop())

    def set_mode(self, mode: str) -> None:
        """Correct the tracked mode without pressing anything."""
        if mode in MODES and mode != self.mode:
            was_going = self.go
            self.set_go(False)
            self.mode = mode
            if was_going:
                self.set_go(True)

    def stop(self) -> None:
        """Release everything (phone gone, keys off, app closing)."""
        self.set_go(False)

    # --- internals ------------------------------------------------------
    async def _push_loop(self) -> None:
        try:
            while True:
                self._kb.press(self._push_key)
                await asyncio.sleep(TAP_S)
                self._kb.release(self._push_key)
                await asyncio.sleep(PUSH_INTERVAL_S - TAP_S)
        except asyncio.CancelledError:
            self._kb.release(self._push_key)
            raise

    def _release_all(self) -> None:
        if self._walk_held:
            self._kb.release(WALK_KEY)
            self._walk_held = False
        if self._push_task is not None:
            self._push_task.cancel()
            self._push_task = None
            self._kb.release(self._push_key)

    def status(self) -> dict:
        return {
            "connected": self.clients > 0,
            "mode": self.mode,
            "go": self.go,
            "y": time.monotonic() < self._y_flash_until,
        }
