"""Per-agent access modes and the UI's answer to a permission prompt."""
import tempfile
import unittest

import app
import council_ext


class AccessModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = council_ext.ModelStore(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ask_is_default_and_never_preapproves_bash(self):
        flags = self.store.flags("claude", "claude")
        self.assertIn("acceptEdits", flags)
        self.assertNotIn("Bash", flags)
        self.assertNotIn("--dangerously-skip-permissions", flags)
        self.assertEqual(self.store.flags("codex", "codex")[:2], ["--sandbox", "workspace-write"])

    def test_full_access_per_agent(self):
        self.assertTrue(self.store.set_access("codex", "full"))
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", self.store.flags("codex", "codex"))
        self.assertNotIn("--sandbox", self.store.flags("codex", "codex"))
        # other agents stay on ask
        self.assertNotIn("--dangerously-skip-permissions", self.store.flags("claude", "claude"))

    def test_model_change_keeps_access(self):
        self.store.set_access("gemini", "full")
        self.store.set("gemini", "agy", "", "high")
        flags = self.store.flags("gemini", "agy")
        self.assertIn("--dangerously-skip-permissions", flags)
        self.assertIn("high", flags)
        self.store.set_access("gemini", "ask")
        self.assertNotIn("--dangerously-skip-permissions", self.store.flags("gemini", "agy"))

    def test_chat_agents_have_no_access_mode(self):
        self.assertFalse(self.store.set_access("gptchat", "full"))
        self.assertEqual(self.store.flags("gptchat", "codex"), [])
        self.assertFalse(self.store.set_access("codex", "root"))


class ApprovalPromptTests(unittest.TestCase):
    def test_finds_the_question_with_context(self):
        screen = "\n".join(["chatter"] * 20 + [
            "Bash command", "  rm -rf build", "Do you want to proceed?",
            "❯ 1. Yes", "  2. No, and tell Claude what to do differently (esc)"])
        req = app._approval_request(screen)
        self.assertIn("rm -rf build", req)
        self.assertIn("1. Yes", req)

    def test_allow_moves_to_the_yes_option(self):
        claude_trust = ("Quick safety check: Is this a project you created or one you trust?\n"
                        " ❯ No, exit\n   Yes, I trust this folder\n Enter to confirm")
        self.assertTrue(app._approval_request(claude_trust))
        self.assertEqual(app._allow_keys(claude_trust), ["Down", "Enter"])
        self.assertEqual(app._allow_keys("Do you trust the contents of this project?\n"
                                         "> Yes, I trust this folder\n  No, exit"), ["Enter"])
        self.assertEqual(app._allow_keys("Do you want to proceed?\n❯ 1. Yes\n  2. No"), ["Enter"])

    def test_quota_is_detected_but_warnings_are_not(self):
        gemini = ("> use mcp to read #general\n⚠ Individual quota reached. Please upgrade your "
                  "subscription to increase your\nlimits. Resets in 117h4m0s.\n────\n>")
        self.assertIn("Individual quota reached", app._quota_hit(gemini))
        self.assertIn("Resets in", app._quota_hit(gemini))
        warn = "⚠ Heads up, you have less than 5% of your 5h limit left.\n› Ask Codex"
        self.assertEqual(app._quota_hit(warn), "")
        old = "Individual quota reached\n" + "\n".join(f"reply {i}" for i in range(20))
        self.assertEqual(app._quota_hit(old), "")  # scrolled away: it works again

    def test_signin_detected(self):
        codex = ("■ Your access token could not be refreshed because you have since logged out "
                 "or signed in to another account. Please sign in again.\n› ")
        self.assertIn("access token", app._signin_needed(codex))
        self.assertEqual(app._signin_needed("› Ask Codex to do anything"), "")

    def test_terminal_keeps_colours_drops_cursor_codes(self):
        raw = "\x1b[?25l\x1b[1;31mred\x1b[0m \x1b[2Kok\x1b]0;title\x07!"
        self.assertEqual(app._NON_SGR_RE.sub("", raw), "\x1b[1;31mred\x1b[0m ok!")
        self.assertNotIn("rm -rf", app._TERM_KEYS)
        self.assertIn("Escape", app._TERM_KEYS)

    def test_idle_screen_is_not_a_prompt(self):
        self.assertEqual(app._approval_request("❯ \n  ? for shortcuts"), "")

    def test_agent_names_are_validated(self):
        self.assertFalse(app._valid_agent("claude; rm -rf /"))


if __name__ == "__main__":
    unittest.main()
