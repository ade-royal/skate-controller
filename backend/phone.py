"""Phone remote: three buttons on an iPhone, served by the backend at /phone.

    Y     taps Y -> Xbox Y (switch walk <-> skate). Stops WALK and PUSH.
    WALK  toggle: holds W -> left stick up (walk forward).
    PUSH  toggle: taps Left Shift -> Xbox A every PUSH_INTERVAL_S (push on the board).

WALK and PUSH are separate buttons because skate.'s mode can't be read: A means
push on the board but jump on foot, so the rider picks the right one.
WALK and PUSH are mutually exclusive.
"""

from __future__ import annotations

import asyncio
import time

Y_KEY = "y"  # tools/keyboard_pad.py: Y -> Xbox Y
WALK_KEY = "w"  # tools/keyboard_pad.py: W -> left stick up
TAP_S = 0.08
PUSH_INTERVAL_S = 0.6  # one push per interval while PUSH is on
FLASH_S = 0.4


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
        self.walk = False
        self.clients = 0
        self._push_task: asyncio.Task | None = None
        self._y_flash_until = 0.0

    @property
    def push(self) -> bool:
        return self._push_task is not None

    # --- buttons --------------------------------------------------------
    async def press_y(self) -> None:
        """Switch walk <-> skate. Stops movement first so you don't roll off."""
        self.stop()
        self._kb.press(Y_KEY)
        await asyncio.sleep(TAP_S)
        self._kb.release(Y_KEY)
        self._y_flash_until = time.monotonic() + FLASH_S

    def set_walk(self, on: bool) -> None:
        self._set_push(False)
        if on and not self.walk:
            self._kb.press(WALK_KEY)
            self.walk = True
        elif not on and self.walk:
            self._kb.release(WALK_KEY)
            self.walk = False

    def set_push(self, on: bool) -> None:
        self.set_walk(False)
        self._set_push(on)

    def stop(self) -> None:
        """Release everything (Y pressed, phone gone, keys off, app closing)."""
        self.set_walk(False)

    # --- internals ------------------------------------------------------
    def _set_push(self, on: bool) -> None:
        if on and self._push_task is None:
            self._push_task = asyncio.create_task(self._push_loop())
        elif not on and self._push_task is not None:
            self._push_task.cancel()
            self._push_task = None
            self._kb.release(self._push_key)

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

    def status(self) -> dict:
        return {
            "connected": self.clients > 0,
            "walk": self.walk,
            "push": self.push,
            "y": time.monotonic() < self._y_flash_until,
        }
