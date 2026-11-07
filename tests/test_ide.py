"""code-server wrapper: trust stays on, only our own process is killed, 0600 password."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ide


class IdeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ide = ide.IDE(self.tmp.name, self.tmp.name)

    def _settings_path(self) -> Path:
        return self.ide.base / "user-data" / "User" / "settings.json"

    def test_defaults_keep_workspace_trust_and_disable_auto_tasks(self):
        self.ide._settings()
        cur = json.loads(self._settings_path().read_text())
        self.assertNotIn("security.workspace.trust.enabled", cur)
        self.assertEqual(cur["task.allowAutomaticTasks"], "off")

    def test_old_trust_switch_off_is_removed_but_user_values_stay(self):
        path = self._settings_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"security.workspace.trust.enabled": False,
                                    "workbench.colorTheme": "Dark", "task.allowAutomaticTasks": "on"}))
        self.ide._settings()
        cur = json.loads(path.read_text())
        self.assertNotIn("security.workspace.trust.enabled", cur)
        self.assertEqual(cur["workbench.colorTheme"], "Dark")
        self.assertEqual(cur["task.allowAutomaticTasks"], "on")  # the user's own choice
        path.write_text(json.dumps({"security.workspace.trust.enabled": True}))
        self.ide._settings()
        self.assertIs(json.loads(path.read_text())["security.workspace.trust.enabled"], True)

    def test_launch_command_has_no_disable_workspace_trust(self):
        src = Path(ide.__file__).read_text()
        self.assertNotIn("--disable-workspace-trust", src)

    @unittest.skipIf(sys.platform == "win32", "POSIX modes")
    def test_password_file_is_0600_from_creation(self):
        modes = []
        real_open = os.open

        def spy(path, flags, mode=0o777, *a, **k):
            fd = real_open(path, flags, mode, *a, **k)
            modes.append(os.fstat(fd).st_mode & 0o777)
            return fd

        with mock.patch.object(ide.os, "open", spy):
            pw = self.ide.password()
        self.assertEqual(modes, [0o600])
        p = self.ide.base / "password"
        self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)
        self.assertEqual(self.ide.password(), pw)
        self.assertEqual([x.name for x in self.ide.base.iterdir()], ["password"])

    @unittest.skipIf(sys.platform == "win32", "uses ps")
    def test_stale_pid_of_unrelated_process_is_never_killed(self):
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)
        self.ide.base.mkdir(parents=True, exist_ok=True)
        (self.ide.base / "pid").write_text(str(sleeper.pid))
        self.assertEqual(self.ide._pid(), 0)
        with mock.patch.object(ide.os, "kill", wraps=os.kill) as k, \
                mock.patch.object(ide.os, "killpg") as kpg:
            self.ide.stop()
        kpg.assert_not_called()
        self.assertFalse([c for c in k.call_args_list if c.args[1] != 0])
        self.assertIsNone(sleeper.poll())

    @unittest.skipIf(sys.platform == "win32", "uses ps")
    def test_pid_file_code_server_is_recognised(self):
        self.ide.base.mkdir(parents=True, exist_ok=True)
        (self.ide.base / "pid").write_text(str(os.getpid()))
        fake = subprocess.CompletedProcess([], 0, "/x/lib/node /x/code-server/4.1/out/node/entry.js\n", "")
        with mock.patch.object(ide.subprocess, "run", return_value=fake) as run:
            self.assertEqual(self.ide._pid(), os.getpid())
        self.assertEqual(run.call_args.args[0][:3], ["ps", "-p", str(os.getpid())])

    def test_own_process_is_trusted(self):
        proc = mock.Mock(pid=4242)
        proc.poll.return_value = None
        self.ide.proc = proc
        self.assertEqual(self.ide._pid(), 4242)

    def test_routes_run_blocking_calls_in_a_thread(self):
        calls = []
        real = asyncio.to_thread

        async def spy(fn, *a, **k):
            calls.append(getattr(fn, "__name__", str(fn)))
            return await real(fn, *a, **k)

        fake = mock.Mock()
        fake.status.__name__ = "status"
        fake.ensure.__name__ = "ensure"
        fake.status.return_value = {"phase": "idle"}
        with mock.patch.object(ide, "ide", fake), mock.patch.object(ide.asyncio, "to_thread", spy):
            asyncio.run(ide.get_ide())
            asyncio.run(ide.start_ide())
        self.assertEqual(calls, ["status", "ensure", "status"])


if __name__ == "__main__":
    unittest.main()
