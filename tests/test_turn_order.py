"""Several agents in one message answer one after another, each after the previous one."""
import asyncio
import unittest

import app


class FakeAgents:
    def __init__(self):
        self.woken = []
        self.offline = set()

    def is_available(self, name):
        return name not in self.offline

    async def trigger(self, name, message="", channel="general", **kw):
        self.woken.append((name, kw.get("prompt", "")))


class TurnOrderTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAgents()
        self.old_agents, app.agents = app.agents, self.fake
        self.old_timeout, app.TURN_TIMEOUT = app.TURN_TIMEOUT, 3600
        app._turns.clear()

    def tearDown(self):
        app.agents = self.old_agents
        app.TURN_TIMEOUT = self.old_timeout
        app._turns.clear()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_only_the_first_is_woken_then_the_next_after_its_answer(self):
        async def flow():
            now = await app._turn_start("general", ["claude", "codex", "gemini"], "user: build it")
            self.assertEqual(now, ["claude"])
            await app._turn_answered("general", "codex")   # not its turn: nothing happens
            self.assertEqual(self.fake.woken, [])
            await app._turn_answered("general", "claude")  # claude answered → codex
            self.assertEqual([w[0] for w in self.fake.woken], ["codex"])
            self.assertIn("already answered", self.fake.woken[0][1])
            await app._turn_answered("general", "codex")   # → gemini
            await app._turn_answered("general", "gemini")  # queue done
            self.assertEqual([w[0] for w in self.fake.woken], ["codex", "gemini"])
            self.assertNotIn("general", app._turns)
        self.run_async(flow())

    def test_offline_agents_are_skipped(self):
        self.fake.offline.add("codex")
        async def flow():
            await app._turn_start("general", ["claude", "codex", "gemini"], "user: hi")
            await app._turn_answered("general", "claude")
            self.assertEqual([w[0] for w in self.fake.woken], ["gemini"])
        self.run_async(flow())

    def test_a_new_request_replaces_the_queue(self):
        async def flow():
            await app._turn_start("general", ["claude", "codex"], "user: one")
            await app._turn_start("general", ["gemini", "claude"], "user: two")
            await app._turn_answered("general", "claude")   # claude is no longer current
            self.assertEqual(self.fake.woken, [])
            await app._turn_answered("general", "gemini")
            self.assertEqual([w[0] for w in self.fake.woken], ["claude"])
        self.run_async(flow())

    def test_default_setting_is_in_turn(self):
        self.assertEqual(app.room_settings.get("turn_order"), "in_turn")


if __name__ == "__main__":
    unittest.main()
