"""Connect AI: config.local.toml round trip, secrets, validation, probe errors."""
import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import connect


class ConnectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        p = mock.patch.object(connect, "ROOT", self.root)
        p.start(); self.addCleanup(p.stop)
        done = subprocess.CompletedProcess([], 1, "", "")
        q = mock.patch.object(connect.subprocess, "run", lambda *a, **k: done)  # no tmux
        q.start(); self.addCleanup(q.stop)
        self.cfg = {"agents": {"claude": {"command": "claude"}, "qwen": {"command": "qwen"}}}
        self.c = connect.Connect(str(self.data), self.cfg, None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_writes_local_config_and_keeps_key_out_of_it(self):
        r = self.c.add({"name": "deepseek", "base_url": "https://api.deepseek.com/v1/", "model": "deepseek-chat",
                        "key": "sk-secret-123", "provider": "deepseek"})
        self.assertIsInstance(r, dict)
        text = (self.root / "config.local.toml").read_text()
        self.assertNotIn("sk-secret-123", text)
        cfg = tomllib.loads(text)["agents"]["deepseek"]
        self.assertEqual(cfg["type"], "api")
        self.assertEqual(cfg["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(connect.read_secret(self.data, "deepseek"), "sk-secret-123")
        if os.name == "posix":
            self.assertEqual(os.stat(self.data / "secrets.json").st_mode & 0o777, 0o600)
        self.assertIn("deepseek", self.cfg["agents"])
        self.assertEqual(self.c.api_agents()[0]["has_key"], True)

    def test_validation(self):
        self.assertIsInstance(self.c.add({"name": "Bad Name", "base_url": "http://x", "model": "m"}), str)
        self.assertIsInstance(self.c.add({"name": "ok", "base_url": "ftp://x", "model": "m"}), str)
        self.assertIsInstance(self.c.add({"name": "ok", "base_url": "http://x"}), str)
        self.assertIn("CLI agent", self.c.add({"name": "claude", "base_url": "http://x", "model": "m"}))

    def test_remove_drops_section_and_secret(self):
        self.c.add({"name": "llama", "base_url": "http://localhost:11434/v1", "model": "llama3.2", "kind": "local"})
        self.c.add({"name": "gpt", "base_url": "https://api.openai.com/v1", "model": "gpt-x", "key": "k"})
        self.assertEqual(self.c.remove("gpt"), "removed")
        local = tomllib.loads((self.root / "config.local.toml").read_text())
        self.assertEqual(list(local["agents"]), ["llama"])
        self.assertEqual(connect.read_secret(self.data, "gpt"), "")
        self.assertIn("no connected", self.c.remove("gpt"))

    def test_toml_escaping(self):
        self.c.add({"name": "qq", "base_url": "http://h/v1", "model": "m", "system_prompt": 'say "hi"\nand \\ bye'})
        cfg = tomllib.loads((self.root / "config.local.toml").read_text())["agents"]["qq"]
        self.assertEqual(cfg["system_prompt"], 'say "hi"\nand \\ bye')

    def test_probe_rejects_bad_urls_and_reports_unreachable(self):
        self.assertFalse(connect.probe("localhost:11434")["ok"])
        r = connect.probe("http://127.0.0.1:9/v1", timeout=1)
        self.assertFalse(r["ok"])
        self.assertIn("not reachable", r["error"])

    def test_catalog_marks_installed_and_team(self):
        with mock.patch.object(connect.shutil, "which", lambda c: "/bin/" + c if c in ("claude", "npm") else None):
            cat = self.c.catalog()
        claude = next(x for x in cat["clis"] if x["id"] == "claude")
        codex = next(x for x in cat["clis"] if x["id"] == "codex")
        self.assertTrue(claude["installed"] and claude["in_team"])
        self.assertFalse(codex["installed"])
        qwen = next(x for x in cat["clis"] if x["id"] == "qwen")
        self.assertFalse(qwen["in_team"])  # a config template without the CLI is not a team member
        self.assertTrue(cat["npm"])
        self.assertIn("council_bridge.py", cat["mcp"]["bridge"]["args"][0])


class ConnectHardeningTests(ConnectTests):
    """Saved keys stay with their URL; secrets/config writes are safe and lossless."""

    def test_probe_with_saved_key_uses_only_stored_url(self):
        self.c.add({"name": "gpt", "base_url": "https://api.openai.com/v1", "model": "m", "key": "sk-1"})
        pick = lambda b: connect.probe_request(self.data, b)
        self.assertEqual(pick({"name": "gpt"}), ("https://api.openai.com/v1", "sk-1"))
        self.assertEqual(pick({"name": "gpt", "base_url": "https://api.openai.com/v1/"}),
                         ("https://api.openai.com/v1", "sk-1"))
        self.assertEqual(pick({"name": "gpt", "base_url": "https://evil.example/v1"}),
                         ("https://evil.example/v1", ""))
        self.assertEqual(pick({"name": "nobody", "base_url": "http://h/v1"}), ("http://h/v1", ""))
        self.assertEqual(pick({"base_url": "http://h/v1", "key": "typed"}), ("http://h/v1", "typed"))

    def test_changing_base_url_without_new_key_drops_saved_key(self):
        self.c.add({"name": "gpt", "base_url": "https://api.openai.com/v1", "model": "m", "key": "sk-1"})
        r = self.c.add({"name": "gpt", "base_url": "https://api.openai.com/v1", "model": "m2"})
        self.assertNotIn("key_dropped", r)
        self.assertEqual(connect.read_secret(self.data, "gpt"), "sk-1")
        r = self.c.add({"name": "gpt", "base_url": "https://other.example/v1", "model": "m2"})
        self.assertTrue(r.get("key_dropped"))
        self.assertEqual(connect.read_secret(self.data, "gpt"), "")
        self.c.add({"name": "gpt", "base_url": "https://third.example/v1", "model": "m2", "key": "sk-2"})
        self.assertEqual(connect.read_secret(self.data, "gpt"), "sk-2")

    @unittest.skipUnless(os.name == "posix", "POSIX modes")
    def test_secret_temp_file_is_0600_from_creation(self):
        modes = []
        real_open = os.open

        def spy(path, flags, mode=0o777, *a, **k):
            fd = real_open(path, flags, mode, *a, **k)
            if str(path).endswith(".tmp"):
                modes.append(os.fstat(fd).st_mode & 0o777)
            return fd

        with mock.patch.object(connect.os, "open", spy):
            connect._write_secret(self.data, "x", "v")
        self.assertEqual(modes, [0o600])
        self.assertEqual(os.stat(self.data / "secrets.json").st_mode & 0o777, 0o600)
        self.assertEqual([p.name for p in self.data.iterdir()], ["secrets.json"])

    def test_concurrent_secret_writes_do_not_lose_keys(self):
        import threading
        threads = [threading.Thread(target=connect._write_secret, args=(self.data, f"a{i}", f"v{i}"))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        data = json.loads((self.data / "secrets.json").read_text())
        self.assertEqual(len(data), 20)

    def test_write_local_keeps_lists_and_nested_tables(self):
        (self.root / "config.local.toml").write_text(
            '[paths]\nworkspace = "/w"\n[server]\nallowed_hosts = ["*"]\nport = 8300\n'
            '[server.extra]\nflag = true\n'
            '[agents.claude]\ncommand = "claude"\nargs = ["--x", "y"]\nenv = { A = "1" }\n'
            '[[hooks]]\nname = "h1"\n')
        self.c.add({"name": "llama", "base_url": "http://localhost:11434/v1", "model": "llama3", "kind": "local"})
        local = tomllib.loads((self.root / "config.local.toml").read_text())
        self.assertEqual(local["server"]["allowed_hosts"], ["*"])
        self.assertEqual(local["server"]["extra"], {"flag": True})
        self.assertEqual(local["paths"]["workspace"], "/w")
        self.assertEqual(local["agents"]["claude"]["args"], ["--x", "y"])
        self.assertEqual(local["agents"]["claude"]["env"], {"A": "1"})
        self.assertEqual(local["hooks"], [{"name": "h1"}])
        self.assertEqual(local["agents"]["llama"]["model"], "llama3")

    def test_color_is_validated(self):
        self.c.add({"name": "aa", "base_url": "http://h/v1", "model": "m", "color": "#12ab"})
        self.c.add({"name": "bb", "base_url": "http://h/v1", "model": "m", "color": 'red;" onload="x'})
        agents = {a["name"]: a["color"] for a in self.c.api_agents()}
        self.assertEqual(agents["aa"], "#12ab")
        self.assertIn(agents["bb"], connect.COLORS)




class AddCliToTeamTests(unittest.TestCase):
    def test_installed_cli_becomes_a_local_agent(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import connect as c
        root = Path(tempfile.mkdtemp())
        (root / "config.local.toml").write_text("[paths]\nworkspace = \"~/w\"\n")
        (root / "council.sh").write_text("")
        cn = c.Connect.__new__(c.Connect)
        cn.config = {"agents": {"claude": {"command": "claude"}}, "paths": {"workspace": "/tmp/w"}}
        with patch.object(c, "ROOT", root), patch.object(c.shutil, "which", lambda cmd: "/bin/" + cmd), \
             patch.object(c.subprocess, "Popen") as popen:
            r = cn.add_cli("gemini-cli")
            self.assertEqual(r["name"], "geminicli")
            local = c._read_local(root)
            self.assertEqual(local["agents"]["geminicli"]["command"], "gemini")
            self.assertEqual(local["paths"]["workspace"], "~/w")  # existing content kept
            self.assertIn("start-one", popen.call_args[0][0])
            self.assertIn("already", cn.add_cli("gemini-cli"))
            self.assertIn("unknown", cn.add_cli("nope"))

if __name__ == "__main__":
    unittest.main()
