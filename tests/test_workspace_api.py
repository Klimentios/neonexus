"""Only the file editing risks: path escape and stale-write protection."""
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import workspace_api


class WorkspaceFileTests(unittest.TestCase):
    def test_read_save_conflict_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "main.py").write_text("print('one')\n")
            (root / ".env").write_text("TOKEN=private\n")
            (Path(tmp) / "secret.txt").write_text("outside")
            workspace_api.configure(str(root), "test-token")
            app = FastAPI()
            app.include_router(workspace_api.router)
            with TestClient(app) as client:
                opened = client.get("/api/workspace/file", params={"path": "main.py"})
                self.assertEqual(opened.status_code, 200)
                revision = opened.json()["revision"]
                saved = client.put("/api/workspace/file", json={
                    "path": "main.py", "content": "print('two')\n", "revision": revision})
                self.assertEqual(saved.status_code, 200)
                self.assertEqual((root / "main.py").read_text(), "print('two')\n")
                self.assertEqual(client.put("/api/workspace/file", json={
                    "path": "main.py", "content": "stale", "revision": revision}).status_code, 409)
                self.assertEqual(client.get("/api/workspace/file", params={
                    "path": "../secret.txt"}).status_code, 404)
                self.assertEqual(client.get("/api/workspace/file", params={
                    "path": ".env"}).status_code, 404)
