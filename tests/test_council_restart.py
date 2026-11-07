"""council_ext: restart is scoped to this install, routes stay off the loop, saves are atomic."""
import asyncio
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import council_ext


class RestartAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _run(self, pids_cwd: dict, comms: dict | None = None):
        comms = comms or {}
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[0] == "pgrep":
                return subprocess.CompletedProcess(cmd, 0, "\n".join(map(str, pids_cwd)) + "\n", "")
            if cmd[0] == "ps":
                return subprocess.CompletedProcess(cmd, 0, comms.get(int(cmd[-1]), "python") + "\n", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        killed, popen = [], []
        with mock.patch.object(council_ext.subprocess, "run", fake_run), \
                mock.patch.object(council_ext.subprocess, "Popen", lambda *a, **k: popen.append((a, k))), \
                mock.patch.object(council_ext, "_pid_cwd", lambda pid: pids_cwd[pid]), \
                mock.patch.object(council_ext.os, "kill", lambda pid, sig: killed.append(pid)):
            council_ext.restart_agent("codex", self.root)
        return calls, killed, popen

    def test_only_this_installs_wrapper_is_killed_and_one_agent_started(self):
        other = "/somewhere/else/agentchattr"
        calls, killed, popen = self._run({101: str(self.root), 102: other, 103: str(self.root.resolve()),
                                          104: str(self.root)}, comms={104: "tmux"})
        self.assertEqual(sorted(killed), [101, 103])  # 102 other install, 104 the tmux server
        self.assertFalse(any(c[0] == "pkill" for c in calls))
        self.assertIn(["pgrep", "-f", "wrapper.py codex( |$)"], calls)
        (args, kw), = popen
        self.assertEqual(args[0], ["/bin/sh", str(self.root / "council.sh"), "start-one", "codex"])
        self.assertEqual(kw["env"]["COUNCIL_NO_OPEN"], "1")

    def test_bad_agent_name_does_nothing(self):
        with mock.patch.object(council_ext.subprocess, "run") as run, \
                mock.patch.object(council_ext.subprocess, "Popen") as popen:
            council_ext.restart_agent("x; rm -rf /", self.root)
        run.assert_not_called()
        popen.assert_not_called()

    def test_council_sh_has_start_one(self):
        sh = (Path(council_ext.__file__).parent / "council.sh").read_text()
        self.assertIn('if [ "$1" = "start-one" ]; then', sh)
        r = subprocess.run(["sh", "-n", str(Path(council_ext.__file__).parent / "council.sh")])
        self.assertEqual(r.returncode, 0)

    def test_routes_restart_through_a_thread(self):
        seen = []
        real = asyncio.to_thread

        async def spy(fn, *a, **k):
            seen.append(fn)
            if fn is council_ext.restart_agent:
                return None
            return await real(fn, *a, **k)

        store = council_ext.ModelStore(self.tmp.name)
        cfg = {"agents": {"claude": {"command": "claude"}}}
        req = mock.Mock()

        async def body():
            return {"preset": "fast"}
        req.json = body
        with mock.patch.object(council_ext, "models", store), mock.patch.object(council_ext, "_config", cfg), \
                mock.patch.object(council_ext.asyncio, "to_thread", spy), \
                mock.patch.object(council_ext, "restart_agent", council_ext.restart_agent):
            asyncio.run(council_ext.put_model("claude", req))
            asyncio.run(council_ext.put_all_models(req))
        self.assertEqual(seen.count(council_ext.restart_agent), 2)


class AtomicSaveTests(unittest.TestCase):
    def test_saves_replace_files_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = council_ext.CouncilStore(tmp)
            replaced = []
            real = os.replace
            with mock.patch.object(council_ext.os, "replace",
                                   lambda a, b: (replaced.append(Path(b).name), real(a, b))):
                store.set_mission("general", "Ship it")
                models = council_ext.ModelStore(tmp)
                models.set_access("claude", "full")
            self.assertEqual(replaced, ["council.json", "agent_models.json"])
            self.assertEqual(json.loads((Path(tmp) / "council.json").read_text())["missions"]["general"]["title"],
                             "Ship it")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["agent_models.json", "council.json"])

    def test_failed_write_keeps_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = council_ext.CouncilStore(tmp)
            store.set_mission("general", "Old")
            with mock.patch.object(council_ext.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    store.set_mission("general", "New")
            self.assertIn("Old", (Path(tmp) / "council.json").read_text())
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["council.json"])


if __name__ == "__main__":
    unittest.main()
