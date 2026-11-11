"""Code mode: task → folder with a git starting point, project, channel, brief; changes; accept; send back."""
import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_existing_git_folder_preserves_uncommitted_work(self):
        folder = self.ws / "app"
        folder.mkdir()
        subprocess.run(["git", "init", "-q", str(folder)], check=True)
        (folder / "draft.txt").write_text("user draft")
        result = self.start(folder="app")
        self.assertIn("uncommitted changes", result)
        self.assertEqual((folder / "draft.txt").read_text(), "user draft")
        self.assertEqual(subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"],
                                        capture_output=True).returncode, 128)

    def test_clean_git_folder_uses_head_without_creating_commit(self):
        folder = self.ws / "app"
        folder.mkdir()
        subprocess.run(["git", "init", "-q", str(folder)], check=True)
        (folder / "existing.txt").write_text("existing")
        subprocess.run(["git", "-C", str(folder), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(folder), "-c", "user.name=Test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "original"], check=True)
        head = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        t = self.start(folder="app")
        self.assertEqual(t["base"], head)
        self.assertEqual(self.cm.changes(t["id"])["files"], [])

    def test_accept_does_not_report_success_when_commit_fails(self):
        t = self.start(folder="hello")
        original_git = codemode._git

        def fail_commit(folder, *args, **kwargs):
            if args and args[0] == "commit":
                return subprocess.CompletedProcess(args, 1, "", "simulated commit failure")
            return original_git(folder, *args, **kwargs)

        with patch.object(codemode, "_git", side_effect=fail_commit):
            result = self.cm.accept(t["id"])
        self.assertIn("simulated commit failure", result)
        self.assertEqual(self.store.get(t["project"])["status"], "active")
        self.assertEqual(self.cm.tasks[t["id"]]["status"], "working")
        self.assertEqual(len(self.posts), 1)


if __name__ == "__main__":
    unittest.main()
