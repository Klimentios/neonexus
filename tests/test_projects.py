"""Projects: goal, done criteria with evidence, review, human-only acceptance."""
import tempfile
import unittest
from pathlib import Path

import projects


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        self.ws.mkdir()
        self.store = projects.ProjectStore(self.tmp.name, str(self.ws))
        self.events = []
        self.store.on_change(lambda k, d: self.events.append(k))
        self.p = self.store.create("Snake Game", "A web snake game", ["runs in browser", "has tests"],
                                   "claude", "general", "claude", "game")


    def test_human_edits_remove_members_and_criteria_and_strings_are_one_item(self):
        p = self.store.create("Edit me", "goal", "single criterion", "user")
        self.assertEqual([c["text"] for c in p["criteria"]], ["single criterion"])
        p = self.store.update(p["id"], "user", human=True, add_members="zed", add_criteria=["two"])
        self.assertEqual(p["members"], ["zed"])
        p = self.store.update(p["id"], "user", human=True, remove_members=["zed"], remove_criteria=[1])
        self.assertEqual(p["members"], [])
        self.assertEqual([c["text"] for c in p["criteria"]], ["two"])
        # agents can't drop criteria
        self.store.update(p["id"], "claude", human=False, remove_criteria=[2])
        self.assertEqual(len(self.store.get(p["id"])["criteria"]), 1)
        # a rejected update changes nothing
        self.assertIsInstance(self.store.update(p["id"], "user", human=True, title="X", mode="bad"), str)
        self.assertEqual(self.store.get(p["id"])["title"], "Edit me")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_slug_and_mirror(self):
        self.assertEqual(self.p["id"], "snake-game")
        again = self.store.create("Snake Game", "second", [], "user")
        self.assertEqual(again["id"], "snake-game-2")
        md = (self.ws / ".council" / "PROJECTS.md").read_text()
        self.assertIn("[ ] runs in browser", md)
        self.assertIn("project", self.events)

    def test_agent_needs_evidence(self):
        r = self.store.check("snake-game", 1, True, "codex", "", human=False)
        self.assertIsInstance(r, str)
        r = self.store.check("snake-game", 1, True, "codex", "opened :8000, screenshot s1.png", human=False)
        self.assertTrue(r["criteria"][0]["done"])
        self.assertEqual(r["status"], "active")

    def test_all_criteria_moves_to_review_and_only_human_accepts(self):
        self.store.check("snake-game", 1, True, "codex", "ok", human=False)
        r = self.store.check("snake-game", 2, True, "codex", "pytest 4 passed", human=False)
        self.assertEqual(r["status"], "review")
        self.assertIsInstance(self.store.update("snake-game", "codex", human=False, status="done"), str)
        r = self.store.update("snake-game", "user", human=True, status="done")
        self.assertEqual(r["status"], "done")
        # accepted: agents can't reopen or tick
        self.assertIsInstance(self.store.check("snake-game", 1, False, "codex", "", human=False), str)
        self.assertIsInstance(self.store.update("snake-game", "codex", human=False, status="active"), str)

    def test_unticking_leaves_review(self):
        self.store.check("snake-game", 1, True, "codex", "ok", human=False)
        self.store.check("snake-game", 2, True, "codex", "ok", human=False)
        r = self.store.check("snake-game", 2, False, "user", "", human=True)
        self.assertEqual(r["status"], "active")

    def test_persistence_and_journal(self):
        self.store.log("snake-game", "gemini", "scaffolded index.html")
        again = projects.ProjectStore(self.tmp.name)
        p = again.get("snake-game")
        self.assertEqual(p["journal"][-1]["text"], "scaffolded index.html")

    def test_validation(self):
        self.assertIsInstance(self.store.create("", "goal", [], "u"), str)
        self.assertIsInstance(self.store.create("t", "g", [], "u", mode="hack"), str)
        self.assertIsInstance(self.store.update("nope", "u", human=True, title="x"), str)
        r = self.store.update("snake-game", "claude", human=False, add_criteria=["deployed"])
        self.assertEqual(r["criteria"][-1]["id"], 3)

    def test_members_join_once(self):
        r = self.store.update("snake-game", "user", human=True, add_members=["codex", "claudechat"])
        self.assertEqual(r["members"], ["codex", "claudechat"])
        r = self.store.update("snake-game", "user", human=True, add_members=["codex"])
        self.assertEqual(r, "nothing to change")
        self.assertIn("team codex, claudechat", projects.summary(self.store.get("snake-game")))


if __name__ == "__main__":
    unittest.main()
