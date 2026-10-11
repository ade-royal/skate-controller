"""Virtual Xbox 360 controller output (Windows, needs the ViGEmBus driver).

`pip install vgamepad` installs the driver on first use. If it's missing, the
pad reports unavailable and the rest of the dashboard keeps working.
"""

from __future__ import annotations


class VirtualPad:
    def __init__(self):
        self.available = False
        self.error = ""
        self._pad = None
        self._last_x = None

    def connect(self) -> bool:
        if self._pad is not None:
            return True
        try:
            import vgamepad

            self._pad = vgamepad.VX360Gamepad()
            self.available = True
            self.error = ""
        except Exception as exc:  # missing package or ViGEmBus driver
            self.available = False
            self.error = f"virtual pad unavailable: {exc}"
        return self.available

    def set_left_stick(self, x: float, y: float = 0.0) -> None:
        if self._pad is None:
            return
        rounded = round(x, 3)
        if rounded == self._last_x:
            return
        self._last_x = rounded
        self._pad.left_joystick_float(x_value_float=x, y_value_float=y)
        self._pad.update()

    def release(self) -> None:
        """Center sticks and release everything so nothing stays held in game."""
        if self._pad is None:
            return
        self._pad.reset()
        self._pad.update()
        self._last_x = None
