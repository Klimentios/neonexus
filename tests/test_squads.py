"""Squads: numbered names, limits, depth, access cap, worktrees."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import council_ext
import squads
from registry import RuntimeRegistry

_real_run = subprocess.run


def _fake_run(cmd, *a, **kw):
    """tmux is faked (nothing starts); git runs for real."""
    if cmd and cmd[0] == "tmux":
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return _real_run(cmd, *a, **kw)


class NumberedRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = RuntimeRegistry(self.tmp.name)
        self.reg.seed({"codex": {"label": "Codex"}, "squad-codex": {"numbered": True}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_main_agent_never_renamed_and_hint_used(self):
        self.assertEqual(self.reg.register("codex")["name"], "codex")
        self.assertEqual(self.reg.register("squad-codex", slot_hint=3)["name"], "squad-codex-3")
        self.assertEqual(self.reg.register("squad-codex")["name"], "squad-codex-1")
        self.assertIn("codex", self.reg.get_all())
        self.reg.deregister("squad-codex-3")
        self.assertIn("squad-codex-1", self.reg.get_all())  # no rename-back to bare base

    def test_hint_ignored_for_normal_bases(self):
        self.assertEqual(self.reg.register("codex", slot_hint=5)["name"], "codex")


class SquadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Path(self.tmp.name) / "lab"
        self.lab.mkdir()
        self.models = council_ext.ModelStore(self.tmp.name)
        self.posts = []
        self.sq = squads.Squads(self.tmp.name, str(self.lab), None, self.models,
                                post=lambda ch, t: self.posts.append(t))
        p1 = mock.patch.object(squads.subprocess, "run", _fake_run)
        p2 = mock.patch.object(squads.threading, "Thread")  # no briefing thread
        p3 = mock.patch.object(squads.Squads, "_alive", lambda self, n: True)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_spawn_makes_worktree_branch_and_name(self):
        m = self.sq.spawn("claude", "codex", "build the parser", "snake")
        self.assertEqual(m["name"], "squad-codex-1")
        self.assertEqual(m["branch"], "squad/squad-codex-1")
        self.assertTrue((Path(m["worktree"]) / "README.md").exists())
        self.assertTrue((self.lab / "projects" / "snake" / ".git").exists())
        self.assertEqual(self.sq.spawn("claude", "codex", "t2", "snake")["name"], "squad-codex-2")

    def test_limits(self):
        for _ in range(3):
            self.assertIsInstance(self.sq.spawn("claude", "claude", "t", "p"), dict)
        self.assertIn("lead 3", self.sq.spawn("claude", "codex", "t", "p"))
        for _ in range(3):
            self.assertIsInstance(self.sq.spawn("codex", "codex", "t", "p"), dict)
        self.assertIn("limit", self.sq.spawn("gemini-x", "codex", "t", "p"))

    def test_depth(self):
        m = self.sq.spawn("claude", "codex", "t", "p")
        m2 = self.sq.spawn(m["name"], "codex", "t", "p")
        self.assertIsInstance(m2, dict)
        self.assertIn("depth", self.sq.spawn(m2["name"], "codex", "t", "p"))

    def test_access_never_exceeds_lead(self):
        self.assertEqual(self.sq.spawn("claude", "codex", "t", "p", access="full")["access"], "ask")
        self.models.set_access("claude", "full")
        self.assertEqual(self.sq.spawn("claude", "codex", "t", "p", access="full")["access"], "full")

    def test_validation_and_stop_rights(self):
        self.assertIsInstance(self.sq.spawn("claude", "gpt", "t", "p"), str)
        self.assertIsInstance(self.sq.spawn("claude", "codex", "t", "../etc"), str)
        self.assertIsInstance(self.sq.spawn("claude", "codex", " ", "p"), str)
        m = self.sq.spawn("claude", "codex", "t", "p")
        self.assertIn("only the lead", self.sq.stop("gemini", m["name"]))
        self.assertIn("stopped", self.sq.stop("claude", m["name"], remove=True))
        self.assertFalse(Path(m["worktree"]).exists())

    def test_status_reports_commits(self):
        m = self.sq.spawn("claude", "codex", "t", "p")
        wt = Path(m["worktree"])
        (wt / "a.py").write_text("x = 1\n")
        _real_run(["git", "add", "a.py"], cwd=wt, check=True)
        _real_run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"],
                  cwd=wt, check=True)
        info = self.sq.status(lead="claude")[0]
        self.assertEqual(info["ahead"], "1")
        self.assertIn("a.py", info["diff"])

    def test_brief_puts_the_task_in_the_prompt_not_a_mention(self):
        woken = []
        self.sq.wake = lambda name, ch, prompt: woken.append((name, prompt))
        m = self.sq.spawn("claude", "codex", "write the lexer", "p")
        self.sq.registry = mock.Mock(get_all=lambda: {"squad-codex-1": {}})  # it came online
        with mock.patch.object(squads.Squads, "_wait_settled", lambda self, m: True):
            self.sq._brief(m)
        self.assertEqual(woken[0][0], "squad-codex-1")
        self.assertIn("YOUR TASK: write the lexer", woken[0][1])
        self.assertNotIn("@squad-codex-1", self.posts[-1])  # the room copy doesn't re-wake it

    def test_report_commits_and_notifies_lead(self):
        m = self.sq.spawn("claude", "gemini", "t", "p")
        self.assertIn("only squad members", self.sq.report("claude", "x"))
        self.assertIn("nothing to hand in", self.sq.report(m["name"], "nothing yet"))
        (Path(m["worktree"]) / "a.py").write_text("print('a')\n")
        r = self.sq.report(m["name"], "added a.py", "python a.py -> a")
        self.assertIn("Handed in", r)
        self.assertTrue(self.posts[-1].startswith("@claude squad-gemini-1 handed in"))
        self.assertEqual(self.sq.members[m["name"]]["review"], "reported")
        self.assertEqual(self.sq._ahead(m), 1)

    def test_two_members_merge_and_conflict(self):
        a = self.sq.spawn("claude", "claude", "part a", "p")
        b = self.sq.spawn("claude", "gemini", "part b", "p")
        c = self.sq.spawn("claude", "codex", "clash", "p")
        (Path(a["worktree"]) / "a.py").write_text("A = 1\n")
        (Path(b["worktree"]) / "b.py").write_text("B = 2\n")
        (Path(c["worktree"]) / "a.py").write_text("A = 99\n")
        for m in (a, b, c):
            self.sq.report(m["name"], "done")
        self.assertIn("only the lead", self.sq.merge("gemini", a["name"]))
        self.assertIn("Merged", self.sq.merge("claude", a["name"]))
        self.assertIn("Merged", self.sq.merge("claude", b["name"]))
        repo = self.lab / "projects" / "p"
        self.assertEqual((repo / "a.py").read_text(), "A = 1\n")
        self.assertTrue((repo / "b.py").exists())
        r = self.sq.merge("claude", c["name"])
        self.assertIn("Conflict", r)
        self.assertIn("a.py", r)
        self.assertEqual((repo / "a.py").read_text(), "A = 1\n")  # main untouched
        self.assertEqual(_real_run(["git", "status", "--porcelain"], cwd=repo,
                                   capture_output=True, text=True).stdout, "")
        self.assertIn("nothing to merge", self.sq.merge("claude", a["name"]))

    def _timeout_on(self, verb):
        def run(cmd, *a, **kw):
            if cmd and cmd[0] == "git" and verb in cmd:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 20))
            return _fake_run(cmd, *a, **kw)
        return mock.patch.object(squads.subprocess, "run", run)

    def test_git_timeouts_return_errors_not_raise(self):
        m = self.sq.spawn("claude", "codex", "t", "p")
        (Path(m["worktree"]) / "a.py").write_text("x\n")
        with self._timeout_on("status"):
            r = self.sq.report(m["name"], "done")
            self.assertTrue(r.startswith("error: git status timed out"), r)
            self.assertTrue(self.sq.merge("claude", m["name"]).startswith("error: git"))
            info = self.sq.status(lead="claude")[0]
            self.assertIn("timed out", info["error"])
        self.assertIn("Handed in", self.sq.report(m["name"], "done"))
        with self._timeout_on("merge"):
            self.assertIn("error: git merge timed out", self.sq.merge("claude", m["name"]))

    def test_git_runs_without_fsmonitor(self):
        seen = []

        def run(cmd, *a, **kw):
            seen.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        with mock.patch.object(squads.subprocess, "run", run):
            squads._git(Path(self.tmp.name), "status", "--porcelain")
        self.assertEqual(seen[0][:4], ["git", "-c", "core.fsmonitor=false", "status"])

    def test_status_reads_a_snapshot_under_the_lock(self):
        self.sq.spawn("claude", "codex", "t", "p")
        held = []
        real_git = squads._git

        def git(*a, **kw):
            held.append(self.sq._lock.locked())
            # a concurrent spawn/stop adding a member must not break the iteration
            self.sq.members.setdefault("squad-x-9", dict(next(iter(self.sq.members.values())), started=0))
            return real_git(*a, **kw)
        with mock.patch.object(squads, "_git", git):
            self.assertEqual(len(self.sq.status(lead="claude")), 1)
        self.assertFalse(any(held), "git must not run while holding the lock")

    def test_message_wakes_member_for_rework(self):
        woken = []
        self.sq.wake = lambda name, ch, prompt: woken.append((name, prompt))
        m = self.sq.spawn("claude", "claude", "t", "p")
        self.assertIn("only the lead", self.sq.message("codex", m["name"], "redo"))
        self.assertEqual(self.sq.message("claude", m["name"], "add tests"), f"Sent to {m['name']}.")
        self.assertIn("add tests", woken[0][1])
        self.assertEqual(self.sq.members[m["name"]]["review"], "rework")

    def test_brief_never_types_into_a_trust_question(self):
        woken = []
        self.sq.wake = lambda name, ch, prompt: woken.append(name)
        m = self.sq.spawn("claude", "claude", "t", "p")
        self.sq.registry = mock.Mock(get_all=lambda: {"squad-claude-1": {}})
        screens = iter(["Quick safety check: Is this a project you created or one you trust?\n"
                        "❯ 1. Yes, I trust this folder"] * 3 + ["> "] * 20)
        clock = iter(range(0, 10000, 3))
        with mock.patch.object(squads.Squads, "_screen", lambda self, n: next(screens)), \
             mock.patch("wrapper_unix.get_ready_checker", lambda *a, **k: (lambda: True)), \
             mock.patch.object(squads.time, "sleep", lambda s: None), \
             mock.patch.object(squads.time, "time", lambda: next(clock)):
            self.sq._brief(m)
        self.assertIn("waits for the user's answer", self.posts[0])
        self.assertEqual(woken, ["squad-claude-1"])  # only after the question was gone
        self.assertTrue(squads.PROMPT_RE.search("Do you trust the contents of this project?"))


class ReadyCheckerTests(unittest.TestCase):
    def _ready(self, screen, provider="claude"):
        import wrapper_unix
        done = subprocess.CompletedProcess([], 0, screen.encode(), b"")
        with mock.patch.object(wrapper_unix.subprocess, "run", lambda *a, **k: done):
            return wrapper_unix.get_ready_checker("x", provider=provider)()

    def test_trust_and_permission_menus_are_not_ready(self):
        self.assertFalse(self._ready("Is this a project you created or one you trust?\n"
                                     " ❯ No, exit\n   Yes, I trust this folder"))
        self.assertFalse(self._ready("Do you want to proceed?\n❯ 1. Yes\n  2. No"))
        self.assertFalse(self._ready("Would you like to run the following command?\n› 1. Yes",
                                     "codex"))
        self.assertTrue(self._ready("╭──╮\n│ ❯  │\n╰──╯\n  ? for shortcuts"))


if __name__ == "__main__":
    unittest.main()
