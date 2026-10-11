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


def test_walk_holds_w_until_toggled_off():
    async def run():
        kb, phone = make()
        phone.set_walk(True)
        assert kb.down == {WALK_KEY} and phone.status()["walk"]
        phone.set_walk(False)
        assert kb.down == set()

    asyncio.run(run())


def test_push_pulses_and_never_holds_w():
    async def run():
        kb, phone = make()
        phone.set_push(True)
        await asyncio.sleep(0.02)
        assert kb.down == {PUSH} and phone.status()["push"]
        phone.set_push(False)
        await asyncio.sleep(0)
        assert kb.down == set() and not phone.status()["push"]

    asyncio.run(run())


def test_walk_and_push_are_mutually_exclusive():
    async def run():
        kb, phone = make()
        phone.set_walk(True)
        phone.set_push(True)
        await asyncio.sleep(0.02)
        assert WALK_KEY not in kb.down and not phone.walk and phone.push
        phone.set_walk(True)
        await asyncio.sleep(0)
        assert PUSH not in kb.down and phone.walk and not phone.push
        phone.stop()

    asyncio.run(run())


def test_y_taps_y_and_stops_movement():
    async def run():
        kb, phone = make()
        phone.set_push(True)
        await phone.press_y()
        assert ("press", Y_KEY) in kb.events and kb.down == set()
        assert not phone.walk and not phone.push and phone.status()["y"]

    asyncio.run(run())
