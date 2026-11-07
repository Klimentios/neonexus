"""VS Code follows NEONEXUS's light / dark skin, but never overrides a theme the user picked."""
import json
import tempfile
import unittest
from pathlib import Path

import ide


class IdeThemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ide = ide.IDE(self.tmp.name, self.tmp.name)
        self.path = Path(self.tmp.name) / "code-server" / "user-data" / "User" / "settings.json"

    def theme(self):
        return json.loads(self.path.read_text())["workbench.colorTheme"]

    def test_follows_dark_and_light(self):
        self.ide.set_theme(True)
        self.assertEqual(self.theme(), "Dark Modern")
        self.ide.set_theme(False)
        self.assertEqual(self.theme(), "Light Modern")

    def test_old_default_names_count_as_ours(self):
        self.ide._settings()
        data = json.loads(self.path.read_text()); data["workbench.colorTheme"] = "Default Light Modern"
        self.path.write_text(json.dumps(data))
        self.ide.set_theme(True)
        self.assertEqual(self.theme(), "Dark Modern")

    def test_user_theme_is_kept(self):
        self.ide._settings()
        data = json.loads(self.path.read_text()); data["workbench.colorTheme"] = "Solarized Dark"
        self.path.write_text(json.dumps(data))
        self.assertEqual(self.ide.set_theme(False), "user theme kept")
        self.assertEqual(self.theme(), "Solarized Dark")


if __name__ == "__main__":
    unittest.main()
