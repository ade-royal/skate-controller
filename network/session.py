"""Read controller states from one connected Raspberry Pi."""

from __future__ import annotations

import socket
from collections.abc import Callable

from controller.movement import CENTER

from network.protocol import StateDecoder

OnState = Callable[[str], None]


def handle_client(
    connection: socket.socket,
    on_state: OnState,
    idle_timeout: float = 1.0,
) -> None:
    """Apply each received state.

    If the Pi stops sending, report CENTER so the laptop can release keys.
    Return when the Pi closes the connection.
    """
    decoder = StateDecoder()
    connection.settimeout(idle_timeout)
    while True:
        try:
            data = connection.recv(1024)
        except socket.timeout:
            on_state(CENTER)
            continue
        if not data:
            return
        for state in decoder.feed(data):
            on_state(state)
