import asyncio
import unittest

from laptop.keyboard_output import KeyPulseOutput


class FakeKeyboard:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(('press', key))

    def release(self, key):
        self.events.append(('release', key))


class KeyPulseTests(unittest.IsolatedAsyncioTestCase):
    async def test_space_is_held_then_released_without_blocking(self):
        keyboard = FakeKeyboard()
        pulse = KeyPulseOutput(keyboard)
        pulse.tap('space', duration_s=0.05)
        self.assertEqual(keyboard.events, [('press', ' ')])
        await asyncio.sleep(0.08)
        self.assertEqual(keyboard.events, [('press', ' '), ('release', ' ')])

    async def test_close_releases_immediately_and_cancels_later_release(self):
        keyboard = FakeKeyboard()
        pulse = KeyPulseOutput(keyboard)
        pulse.tap('x', duration_s=0.05)
        pulse.close()
        pulse.close()
        await asyncio.sleep(0.08)
        self.assertEqual(keyboard.events, [('press', 'x'), ('release', 'x')])

    async def test_rebinding_does_not_leave_old_key_pressed(self):
        keyboard = FakeKeyboard()
        pulse = KeyPulseOutput(keyboard)
        pulse.tap('space')
        pulse.tap('x')
        pulse.close()
        self.assertEqual(keyboard.events,
                         [('press', ' '), ('release', ' '), ('press', 'x'), ('release', 'x')])
