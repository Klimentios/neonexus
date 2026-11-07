"""screen_state: prompts, quota and sign-in only from the CLI itself, not agent prose."""
import unittest

import screen_state as ss


class ScreenStateTests(unittest.TestCase):
    def test_real_prompts(self):
        self.assertTrue(ss.waiting_for_human("Bash command\n  rm -rf build\nDo you want to proceed?\n❯ 1. Yes\n  2. No"))
        self.assertTrue(ss.waiting_for_human("Is this a project you created or one you trust?\n ❯ No, exit\n   Yes, I trust this folder"))
        self.assertTrue(ss.waiting_for_human("Would you like to run the following command?\n› 1. Yes, proceed (y)\n  2. No (esc)"))
        self.assertTrue(ss.waiting_for_human("Do you trust the contents of this project?\n> Yes, I trust this folder\n  No, exit"))

    def test_prose_is_not_a_prompt(self):
        self.assertFalse(ss.waiting_for_human("● The deploy requires approval from the user, so I stopped.\n\n❯ \n  ? for shortcuts"))
        self.assertFalse(ss.waiting_for_human("I asked: Do you want to proceed? and waited.\n› Ask Codex to do anything"))

    def test_old_prompt_scrolled_up(self):
        old = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n" + "\n".join(f"line {i}" for i in range(30))
        self.assertFalse(ss.waiting_for_human(old))

    def test_quota_and_signin_need_the_cli_marker(self):
        self.assertIn("quota", ss.quota_hit("> hi\n⚠ Individual quota reached. Please upgrade your subscription"))
        self.assertEqual(ss.quota_hit("Claude: Gemini says 'Individual quota reached' until Friday.\n❯ "), "")
        self.assertIn("access token", ss.signin_needed("■ Your access token could not be refreshed. Please sign in again.\n› "))
        self.assertEqual(ss.signin_needed("Codex printed: Please sign in again — so it is logged out.\n❯ "), "")
        self.assertIn("authenticate", ss.signin_needed("How would you like to authenticate?\n 1. Google"))


if __name__ == "__main__":
    unittest.main()
