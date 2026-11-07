"""Code mode: task → folder with a git starting point, project, channel, brief; changes; accept; send back."""
import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import codemode
import projects


@unittest.skipUnless(shutil.which("git"), "git is required")
class CodeModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ws = root / "ws"
        self.ws.mkdir()
        self.store = projects.ProjectStore(str(root / "data"), str(self.ws))
        self.posts, self.channels = [], []

        async def ensure(name):
            self.channels.append(name)
        self.cm = codemode.CodeMode(str(root / "data"), str(self.ws), self.store,
                                    post=lambda ch, s, t: self.posts.append((ch, s, t)), ensure_channel=ensure)

    def start(self, **kw):
        args = {"task": "Make a hello script", "folder": "", "builder": "codex", "reviewer": "claude", **kw}
        return asyncio.run(self.cm.start(**args))

    def test_start_prepares_everything_and_briefs_builder_then_reviewer(self):
        t = self.start()
        self.assertEqual(t["folder"], "make-a-hello-s")
        self.assertTrue((self.ws / t["folder"] / ".git").is_dir())
        self.assertEqual(self.channels, [t["channel"]])
        self.assertTrue(t["channel"].startswith("code-"))
        p = self.store.get(t["project"])
        self.assertEqual(p["lead"], "codex")
        self.assertIn("claude", p["members"])
        self.assertEqual(len(p["criteria"]), 3)
        ch, sender, text = self.posts[0]
        self.assertEqual((ch, sender), (t["channel"], "user"))
        # builder first, reviewer second: the room's turn order wakes them in this order
        self.assertLess(text.index("@codex"), text.index("@claude"))

    def test_changes_accept_and_send_back(self):
        t = self.start(folder="hello")
        (self.ws / "hello" / "hello.py").write_text("print('hi')\n")
        ch = self.cm.changes(t["id"])
        self.assertIn("hello.py", ch["files"])
        self.assertIn("print('hi')", ch["diff"])
        self.cm.send_back(t["id"], "add a test")
        self.assertIn("@codex not done yet: add a test", self.posts[-1][2])
        self.cm.accept(t["id"])
        self.assertEqual(self.store.get(t["project"])["status"], "done")
        log = subprocess.run(["git", "-C", str(self.ws / "hello"), "log", "--oneline"], capture_output=True, text=True).stdout
        self.assertIn("Code mode: Make a hello script", log)
        self.assertEqual(self.cm.changes(t["id"])["files"], ["hello.py"])  # still vs the starting point

    def test_folder_must_stay_inside_the_workspace(self):
        for bad in ("../outside", "/etc", ".git"):
            self.assertIsInstance(self.start(folder=bad), str)
        self.assertIsInstance(self.start(builder=""), str)
        self.assertIsInstance(self.start(task="x"), str)

    def test_existing_folder_keeps_its_files_in_the_starting_point(self):
        (self.ws / "app").mkdir()
        (self.ws / "app" / "old.txt").write_text("old")
        t = self.start(folder="app", reviewer="")
        self.assertEqual(self.cm.changes(t["id"])["files"], [])
        self.assertNotIn("Then @", self.posts[-1][2])
        self.assertEqual(self.cm.folders(), ["app"])


if __name__ == "__main__":
    unittest.main()
