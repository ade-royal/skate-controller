import unittest
from unittest.mock import patch

from backend.server import App


class FakeKeyboard:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(('press', key))

    def release(self, key):
        self.events.append(('release', key))


class BackendPopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.keyboard = FakeKeyboard()
        self.keyboard_patch = patch('backend.server.pynput_keyboard', return_value=self.keyboard)
        self.keyboard_patch.start()
        self.save_patch = patch('backend.server.save_config')
        self.saved = self.save_patch.start()
        self.app = App({'pi_password': ''})

    def tearDown(self):
        self.app.shutdown()
        self.save_patch.stop()
        self.keyboard_patch.stop()

    def sample(self, t, y, acceleration=None):
        with patch('backend.server.time.monotonic', return_value=t):
            self.app.on_packet({'a': acceleration or [0, 0.008, 1], 'g': [0, y, 0]})
        self.app.update_pop(t)

    def pop(self, start=100):
        for dt, y in [(0, -60), (.2, -20), (.4, 0), (.6, 50)]:
            self.sample(start + dt, y)

    def pop_presses(self):
        return [event for event in self.keyboard.events if event == ('press', ' ')]

    async def test_default_pop_sends_one_space_at_broadcast_tick(self):
        self.pop()
        self.assertEqual(self.pop_presses(), [('press', ' ')])

    async def test_pop_off_preserves_steering_and_persists(self):
        self.app.set_pop_enabled(False)
        self.pop()
        self.sample(102, 0, [0, -.1, 1])
        self.assertFalse(self.pop_presses())
        self.assertIn(('press', 'a'), self.keyboard.events)
        self.assertFalse(self.saved.call_args.args[0]['pop_enabled'])
        self.assertFalse(self.app.snapshot()['pop_enabled'])

    async def test_global_keys_off_blocks_pop(self):
        self.app.set_keys_enabled(False)
        self.pop()
        self.assertFalse(self.pop_presses())

    async def test_disabling_during_dip_cannot_fire_on_reenable(self):
        self.sample(100, -60)
        self.app.set_pop_enabled(False)
        self.app.set_pop_enabled(True)
        self.sample(100.2, 60)
        self.assertFalse(self.pop_presses())

    async def test_disable_during_pulse_releases_space_immediately(self):
        self.pop()
        self.app.set_pop_enabled(False)
        self.assertIn(('release', ' '), self.keyboard.events)

    async def test_sensor_error_clears_pending_motion(self):
        self.sample(100, -60)
        self.app.on_packet({'err': 'sensor disconnected'})
        self.sample(100.2, 60)
        self.assertFalse(self.pop_presses())

    async def test_stale_feed_cannot_fire(self):
        self.sample(100, -60)
        self.app.tele['g'] = [0, 60, 0]
        self.app.update_pop(102)
        self.assertFalse(self.pop_presses())

    async def test_pop_binding_changes_output_and_conflicts_are_rejected(self):
        self.app.rebind('pop', 'a')
        self.assertEqual(self.app.config['pop_key'], 'space')
        self.app.rebind('pop', 'x')
        self.app.rebind('left', 'x')
        self.assertEqual(self.app.config['left_key'], 'a')
        self.pop()
        self.assertIn(('press', 'x'), self.keyboard.events)
        self.assertFalse(self.pop_presses())

    async def test_saved_off_state_survives_new_app(self):
        self.app.set_pop_enabled(False)
        replacement = App(dict(self.app.config))
        try:
            self.assertFalse(replacement.config['pop_enabled'])
        finally:
            replacement.shutdown()
