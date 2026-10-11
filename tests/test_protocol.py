"""Network message tests. No Raspberry Pi and no keyboard required."""

from __future__ import annotations

import socket
import threading
import time
import unittest

from network.protocol import StateDecoder, decode_state, encode_state, encode_update
from network.session import handle_client


class ProtocolTests(unittest.TestCase):
    def test_encode_states(self) -> None:
        self.assertEqual(encode_state("LEFT"), b"LEFT\n")
        self.assertEqual(encode_state("CENTER"), b"CENTER\n")
        self.assertEqual(encode_state("RIGHT"), b"RIGHT\n")

    def test_decode_round_trip(self) -> None:
        for state in ("LEFT", "CENTER", "RIGHT"):
            self.assertEqual(decode_state(encode_state(state).decode("ascii")), state)

    def test_reject_unknown_state(self) -> None:
        with self.assertRaises(ValueError):
            encode_state("forward")
        with self.assertRaises(ValueError):
            decode_state("left")

    def test_ollie_is_sent_beside_steering(self) -> None:
        self.assertEqual(encode_update("RIGHT", "OLLIE"), b"RIGHT\nOLLIE\n")
        self.assertEqual(encode_update("LEFT"), b"LEFT\n")
        self.assertEqual(
            StateDecoder().feed(encode_update("RIGHT", "OLLIE")),
            ["RIGHT", "OLLIE"],
        )

    def test_decoder_waits_for_a_full_line(self) -> None:
        decoder = StateDecoder()
        self.assertEqual(decoder.feed(b"LE"), [])
        self.assertEqual(decoder.feed(b"FT\nCEN"), ["LEFT"])
        self.assertEqual(decoder.feed(b"TER\nRIGHT\n"), ["CENTER", "RIGHT"])


class SessionTests(unittest.TestCase):
    def test_idle_connection_reports_center_then_later_states(self) -> None:
        client, server = socket.socketpair()
        received: list[str] = []
        client.settimeout(2)
        server.settimeout(2)

        def run() -> None:
            handle_client(server, received.append, idle_timeout=0.2)

        worker = threading.Thread(target=run)
        worker.start()
        try:
            client.sendall(encode_state("LEFT"))
            deadline = time.time() + 2
            while "CENTER" not in received and time.time() < deadline:
                time.sleep(0.05)
            client.sendall(encode_state("RIGHT"))
            deadline = time.time() + 2
            while "RIGHT" not in received and time.time() < deadline:
                time.sleep(0.05)
        finally:
            client.close()
            worker.join(timeout=2)
            server.close()

        self.assertFalse(worker.is_alive())
        self.assertEqual(received[0], "LEFT")
        right_at = received.index("RIGHT")
        self.assertIn("CENTER", received[:right_at])
        self.assertIn("RIGHT", received)

    def test_keyboard_interrupt_leaves_the_read_loop(self) -> None:
        client, server = socket.socketpair()

        def on_state(state: str) -> None:
            if state == "LEFT":
                raise KeyboardInterrupt

        client.sendall(encode_state("LEFT"))
        try:
            with self.assertRaises(KeyboardInterrupt):
                handle_client(server, on_state, idle_timeout=0.2)
        finally:
            client.close()
            server.close()

    def test_center_waits_for_the_full_idle_timeout(self) -> None:
        client, server = socket.socketpair()
        marks: list[tuple[float, str]] = []

        def on_state(state: str) -> None:
            marks.append((time.monotonic(), state))

        def run() -> None:
            handle_client(server, on_state, idle_timeout=0.6)

        worker = threading.Thread(target=run)
        worker.start()
        try:
            client.sendall(encode_state("LEFT"))
            deadline = time.time() + 2
            while not any(state == "CENTER" for _, state in marks) and time.time() < deadline:
                time.sleep(0.05)
        finally:
            client.close()
            worker.join(timeout=2)
            server.close()

        self.assertFalse(worker.is_alive())
        left_at = next(stamp for stamp, state in marks if state == "LEFT")
        center_at = next(stamp for stamp, state in marks if state == "CENTER")
        self.assertGreaterEqual(center_at - left_at, 0.45)


if __name__ == "__main__":
    unittest.main()
