"""Shutdown tests for the laptop receiver. No MPU-6050 and no pynput."""

from __future__ import annotations

import socket
import threading
import time
import unittest

from network.session import poll_accept
from scripts.laptop_receiver import close_socket, run_until_stopped


class CloseTracker:
    def __init__(self) -> None:
        self.closes = 0

    def close(self) -> None:
        self.closes += 1


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def setsockopt(self, *_args) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeServer:
    """Listening socket that times out twice, then raises KeyboardInterrupt."""

    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    def settimeout(self, _timeout: float) -> None:
        return None

    def accept(self):
        self.calls += 1
        if self.calls < 3:
            raise TimeoutError
        raise KeyboardInterrupt

    def close(self) -> None:
        self.closed = True


class OneShotServer:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.closed = False
        self._accepted = False

    def settimeout(self, _timeout: float) -> None:
        return None

    def accept(self):
        if not self._accepted:
            self._accepted = True
            return (self.connection, ("10.0.0.2", 1234))
        raise KeyboardInterrupt

    def close(self) -> None:
        self.closed = True


class ReceiverShutdownTests(unittest.TestCase):
    def test_poll_accept_returns_without_a_client(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        try:
            started = time.monotonic()
            accepted = poll_accept(server, poll_timeout=0.2)
            elapsed = time.monotonic() - started
        finally:
            server.close()
        self.assertIsNone(accepted)
        self.assertLess(elapsed, 1.0)

    def test_keyboard_interrupt_while_waiting_closes_the_socket_and_keys(self) -> None:
        server = FakeServer()
        output = CloseTracker()
        with self.assertRaises(KeyboardInterrupt):
            run_until_stopped(server, output, lambda _connection: None)
        self.assertTrue(server.closed)
        self.assertGreaterEqual(output.closes, 1)
        self.assertGreaterEqual(server.calls, 2)

    def test_exception_while_connected_releases_keys_and_closes_sockets(self) -> None:
        server = OneShotServer()
        output = CloseTracker()

        def on_connection(_connection) -> None:
            raise RuntimeError("failed while a key was held")

        with self.assertRaises(RuntimeError):
            run_until_stopped(server, output, on_connection)
        self.assertTrue(server.connection.closed)
        self.assertTrue(server.closed)
        self.assertGreaterEqual(output.closes, 1)

    def test_disconnect_still_accepts_the_next_client(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        output = CloseTracker()
        seen: list[int] = []

        def on_connection(connection: socket.socket) -> None:
            seen.append(connection.getpeername()[1])
            connection.settimeout(1)
            while True:
                try:
                    data = connection.recv(1024)
                except TimeoutError:
                    break
                if not data:
                    break
            if len(seen) == 2:
                raise KeyboardInterrupt

        def clients() -> None:
            for _ in range(2):
                client = None
                for _attempt in range(40):
                    try:
                        client = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                        break
                    except OSError:
                        time.sleep(0.05)
                if client is None:
                    return
                client.sendall(b"LEFT\n")
                client.close()
                time.sleep(0.15)

        worker = threading.Thread(target=clients)
        worker.start()
        try:
            with self.assertRaises(KeyboardInterrupt):
                run_until_stopped(server, output, on_connection)
        finally:
            worker.join(timeout=3)
            close_socket(server)

        self.assertEqual(len(seen), 2)
        self.assertGreaterEqual(output.closes, 2)
        self.assertEqual(server.fileno(), -1)


if __name__ == "__main__":
    unittest.main()
