"""Phone remote key logic. No phone, network or real keyboard needed."""

import asyncio

from backend.phone import WALK_KEY, Y_KEY, PhoneRemote

PUSH = "PUSH"


class FakeKeyboard:
    def __init__(self):
        self.events = []
        self.down = set()

    def press(self, key):
        self.events.append(("press", key))
        self.down.add(key)

    def release(self, key):
        self.events.append(("release", key))
        self.down.discard(key)


def make():
    kb = FakeKeyboard()
    return kb, PhoneRemote(keyboard=kb, push_key=PUSH)


def test_go_in_walk_mode_holds_w_until_toggled_off():
    async def run():
        kb, phone = make()
        phone.set_go(True)
        assert kb.down == {WALK_KEY}
        phone.set_go(False)
        assert kb.down == set()

    asyncio.run(run())


def test_y_taps_y_switches_mode_and_stops_go():
    async def run():
        kb, phone = make()
        phone.set_go(True)
        await phone.press_y()
        assert phone.mode == "skate" and not phone.go
        assert ("press", Y_KEY) in kb.events and kb.down == set()

    asyncio.run(run())


def test_go_in_skate_mode_pulses_push_and_releases_on_stop():
    async def run():
        kb, phone = make()
        phone.set_mode("skate")
        phone.set_go(True)
        await asyncio.sleep(0.02)
        assert kb.down == {PUSH}
        phone.stop()
        await asyncio.sleep(0)
        assert kb.down == set() and not phone.go

    asyncio.run(run())


def test_mode_correction_keeps_go_running_in_new_mode():
    async def run():
        kb, phone = make()
        phone.set_go(True)
        phone.set_mode("skate")
        await asyncio.sleep(0.02)
        assert WALK_KEY not in kb.down and PUSH in kb.down
        phone.stop()

    asyncio.run(run())
