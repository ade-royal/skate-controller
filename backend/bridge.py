"""Run tools/keyboard_pad.py (keys -> virtual Xbox pad) as a child process."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATE_NO_WINDOW = 0x08000000


class Bridge:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self.error = ""

    @property
    def running(self) -> bool:
        if self._proc is not None and self._proc.poll() is not None:
            code = self._proc.returncode
            self._proc = None
            self.error = f"Xbox bridge stopped (exit {code}). Toggle it on to retry."
        return self._proc is not None

    def start(self) -> None:
        if self.running:
            return
        self.error = ""
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "tools.keyboard_pad"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self.error = ""
