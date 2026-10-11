"""Read controller states from one connected Raspberry Pi."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable

from controller.movement import CENTER

from network.protocol import StateDecoder

OnState = Callable[[str], None]

# Windows does not raise KeyboardInterrupt while accept() or recv() is
# blocked with no timeout. Return to Python this often so Ctrl+C can stop
# the laptop receiver. This does not change how soon a silent Pi becomes CENTER.
POLL_SECONDS = 0.2


def poll_accept(
    server: socket.socket,
    poll_timeout: float = POLL_SECONDS,
) -> tuple | None:
    """Accept one client, or return None when the poll window expires."""
    server.settimeout(poll_timeout)
    try:
        return server.accept()
    except TimeoutError:
        return None


def handle_client(
    connection: socket.socket,
    on_state: OnState,
    idle_timeout: float = 1.0,
) -> None:
    """Apply each received state.

    If the Pi stops sending for idle_timeout seconds, report CENTER so the
    laptop can release keys. Return when the Pi closes the connection.
    recv() itself wakes every POLL_SECONDS so Ctrl+C is not stuck inside it.
    """
    decoder = StateDecoder()
    connection.settimeout(min(POLL_SECONDS, idle_timeout))
    next_center_at = time.monotonic() + idle_timeout
    while True:
        try:
            data = connection.recv(1024)
        except TimeoutError:
            now = time.monotonic()
            if now >= next_center_at:
                on_state(CENTER)
                next_center_at = now + idle_timeout
            continue
        if not data:
            return
        next_center_at = time.monotonic() + idle_timeout
        for state in decoder.feed(data):
            on_state(state)
