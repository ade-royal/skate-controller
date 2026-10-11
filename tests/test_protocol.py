"""Network message tests. No Raspberry Pi and no keyboard required."""

from __future__ import annotations

import socket
import threading
import time
import unittest

from network.protocol import StateDecoder, decode_state, encode_state
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


if __name__ == "__main__":
    unittest.main()
