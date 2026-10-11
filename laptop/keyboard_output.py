"""Laptop-side keyboard output adapter."""


def command_to_key(command):
    """Translate movement commands to keyboard keys."""
    return {
        "forward": "w",
        "backward": "s",
        "left": "a",
        "right": "d",
    }.get(command)
