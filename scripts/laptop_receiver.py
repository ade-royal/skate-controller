"""Receive LEFT, CENTER, and RIGHT and hold the mapped keys.

Run this on the Windows laptop from the repository root:

    python scripts/laptop_receiver.py

Find this computer's IPv4 address with ipconfig, then point the Raspberry Pi
at that address. Use --dry-run to print states without pressing keys.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laptop.keyboard_output import KeyBindings, KeyboardOutput, NullKeyboard, pynput_keyboard
from network.protocol import DEFAULT_PORT
from network.session import handle_client


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turn skateboard states into keys.")
    parser.add_argument("--host", default="0.0.0.0", help="Address to listen on.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--left-key", default="a", help="Key held for LEFT.")
    parser.add_argument("--right-key", default="d", help="Key held for RIGHT.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print controller states without pressing keys.",
    )
    return parser.parse_args(argv)


def ipv4_hints() -> list[str]:
    """IPv4 addresses Python can see for this computer."""
    found: list[str] = []
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return found
    for info in infos:
        address = info[4][0]
        if address.startswith("127.") or address in found:
            continue
        found.append(address)
    return found


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    bindings = KeyBindings(args.left_key, args.right_key)
    if args.dry_run:
        keyboard = NullKeyboard()
    else:
        keyboard = pynput_keyboard()
    output = KeyboardOutput(bindings, keyboard=keyboard)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((args.host, args.port))
        server.listen(1)
        _print_banner(args, bindings)
        while True:
            print("Waiting for the Raspberry Pi...")
            connection, address = server.accept()
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"Connected to {address[0]}:{address[1]}")
            try:
                handle_client(connection, lambda state: _on_state(output, state))
                print("Raspberry Pi disconnected.")
            finally:
                output.close()
                connection.close()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        output.close()
        server.close()


def _on_state(output: KeyboardOutput, state: str) -> None:
    if output.apply_state(state):
        print(output.status_line(), flush=True)


def _print_banner(args: argparse.Namespace, bindings: KeyBindings) -> None:
    mode = "dry run, no keys will be pressed" if args.dry_run else "keys will be pressed"
    print(f"Listening on {args.host}:{args.port} ({mode})")
    print(f"LEFT holds {bindings.left!r}    RIGHT holds {bindings.right!r}    CENTER releases both")
    hints = ipv4_hints()
    if hints:
        print("IPv4 addresses seen from Python: " + ", ".join(hints))
    print("If the Pi cannot connect, run ipconfig and use the hotspot IPv4 address.")
    print("Ctrl+C releases the steering keys and stops.")


if __name__ == "__main__":
    main()
