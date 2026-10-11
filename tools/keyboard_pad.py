"""Drive the virtual Xbox pad from the keyboard (skate. on PC is controller-only).

Usage (Windows):
    python -m tools.keyboard_pad

Lets you test the game and a scene before the board is tuned, and checks that
the game accepts the virtual pad. Keys are read globally, so it works while the
game window has focus. F8 pauses/resumes; Ctrl+C quits and releases everything.

    WASD / arrows   left stick (steer)       Space       ollie (right-stick flick)
    I J K L         right stick (manual)     Left Shift  A (push / confirm)
    Enter           A                        Left Ctrl   X (mongo push)
    Backspace       B (back)                 Y           Y
    Q / E           LB / RB                  Z / C       LT / RT
    T F G H         D-pad up/left/down/right Tab / P     View / Menu
"""

from __future__ import annotations

import ctypes
import time

import vgamepad as vg

POLL_S = 1 / 120
# Ollie in skate.: pull the right stick down (crouch), then flick it up (pop).
OLLIE_DOWN_S = 0.15
OLLIE_UP_S = 0.10

VK = {
    "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C,
    "SPACE": 0x20, "LSHIFT": 0xA0, "LCTRL": 0xA2, "ENTER": 0x0D, "BACK": 0x08,
    "TAB": 0x09, "P": 0x50, "Q": 0x51, "E": 0x45, "Z": 0x5A, "C": 0x43,
    "T": 0x54, "F": 0x46, "G": 0x47, "H": 0x48, "X": 0x58, "Y": 0x59, "F8": 0x77,
}

B = vg.XUSB_BUTTON
BUTTONS = {
    B.XUSB_GAMEPAD_A: ("LSHIFT", "ENTER"),
    B.XUSB_GAMEPAD_B: ("BACK",),
    B.XUSB_GAMEPAD_X: ("LCTRL", "X"),
    B.XUSB_GAMEPAD_Y: ("Y",),
    B.XUSB_GAMEPAD_LEFT_SHOULDER: ("Q",),
    B.XUSB_GAMEPAD_RIGHT_SHOULDER: ("E",),
    B.XUSB_GAMEPAD_BACK: ("TAB",),
    B.XUSB_GAMEPAD_START: ("P",),
    B.XUSB_GAMEPAD_DPAD_UP: ("T",),
    B.XUSB_GAMEPAD_DPAD_LEFT: ("F",),
    B.XUSB_GAMEPAD_DPAD_DOWN: ("G",),
    B.XUSB_GAMEPAD_DPAD_RIGHT: ("H",),
}

_user32 = ctypes.windll.user32


def down(name: str) -> bool:
    return bool(_user32.GetAsyncKeyState(VK[name]) & 0x8000)


def axis(negative: tuple[str, ...], positive: tuple[str, ...]) -> float:
    return float(any(down(k) for k in positive)) - float(any(down(k) for k in negative))


def main() -> None:
    pad = vg.VX360Gamepad()
    print(__doc__)
    enabled, f8_was_down = True, False
    ollie_started: float | None = None
    space_was_down = False
    try:
        while True:
            f8 = down("F8")
            if f8 and not f8_was_down:
                enabled = not enabled
                pad.reset()
                pad.update()
                print("keyboard pad", "ON" if enabled else "PAUSED")
            f8_was_down = f8
            if not enabled:
                time.sleep(POLL_S)
                continue

            pad.left_joystick_float(
                x_value_float=axis(("A", "LEFT"), ("D", "RIGHT")),
                y_value_float=axis(("S", "DOWN"), ("W", "UP")),
            )

            space = down("SPACE")
            now = time.monotonic()
            if space and not space_was_down and ollie_started is None:
                ollie_started = now
            space_was_down = space
            if ollie_started is not None:
                elapsed = now - ollie_started
                if elapsed < OLLIE_DOWN_S:
                    pad.right_joystick_float(x_value_float=0.0, y_value_float=-1.0)
                elif elapsed < OLLIE_DOWN_S + OLLIE_UP_S:
                    pad.right_joystick_float(x_value_float=0.0, y_value_float=1.0)
                else:
                    ollie_started = None
            if ollie_started is None:
                pad.right_joystick_float(x_value_float=axis(("J",), ("L",)), y_value_float=axis(("K",), ("I",)))

            for button, keys in BUTTONS.items():
                if any(down(k) for k in keys):
                    pad.press_button(button=button)
                else:
                    pad.release_button(button=button)
            pad.left_trigger_float(value_float=1.0 if down("Z") else 0.0)
            pad.right_trigger_float(value_float=1.0 if down("C") else 0.0)
            pad.update()
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    finally:
        pad.reset()
        pad.update()


if __name__ == "__main__":
    main()
