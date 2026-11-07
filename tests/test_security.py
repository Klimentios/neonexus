"""Browser-facing security: Host (DNS rebinding), Origin, token-free role reads only,
SVG uploads sandboxed, malformed bodies are 400 not 500."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import app

TOKEN = "sec-test"


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.config = {"server": {"port": 8300}, "images": {"upload_dir": str(self.root)}}
        api = FastAPI()

        @api.get("/")
        async def index():
            return {"page": f"__SESSION_TOKEN__={TOKEN}"}

        @api.get("/api/roles")
        async def roles():
            return {"claude": "Architect"}

        @api.post("/api/roles/{name}")
        async def set_role(name: str, request: Request):
            return {"ok": True}

        @api.post("/api/echo")
        async def echo(request: Request):
            return await request.json()

        api.add_api_route("/uploads/{filename}", app.serve_upload, methods=["GET"])
        api.add_exception_handler(app.json.JSONDecodeError, app._bad_json)
        for name, value in {"app": api, "config": self.config, "registry": None,
                            "session_token": TOKEN}.items():
            self.stack.enter_context(patch.object(app, name, value))
        app._install_security_middleware(TOKEN, self.config)
        self.client = self.stack.enter_context(TestClient(api, base_url="http://127.0.0.1:8300"))

    def test_foreign_host_cannot_read_the_page_or_the_api(self):
        r = self.client.get("/", headers={"Host": "attacker.example:8300"})
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(TOKEN, r.text)
        r = self.client.get("/", headers={"Host": "127.0.0.1:8300"})
        self.assertEqual(r.status_code, 200)

    def test_roles_can_be_read_but_not_written_without_token(self):
        self.assertEqual(self.client.get("/api/roles").status_code, 200)
        r = self.client.post("/api/roles/claude", content='{"role":"x"}',
                             headers={"Content-Type": "text/plain", "Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/roles/claude", json={"role": "x"}, headers={"X-Session-Token": TOKEN})
        self.assertEqual(r.status_code, 200)

    def test_foreign_origin_is_rejected(self):
        r = self.client.post("/api/echo", json={}, headers={"X-Session-Token": TOKEN,
                                                           "Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_malformed_json_is_400(self):
        r = self.client.post("/api/echo", content="{not json",
                             headers={"X-Session-Token": TOKEN, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)

    def test_svg_uploads_are_sandboxed(self):
        (self.root / "a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        r = self.client.get("/uploads/a.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sandbox", r.headers.get("content-security-policy", ""))
        self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")

    def test_websocket_check_needs_our_host_and_origin(self):
        class WS:
            def __init__(self, host, origin=None):
                self.headers = {"host": host, **({"origin": origin} if origin else {})}
        self.assertTrue(app.ws_allowed(WS("127.0.0.1:8300", "http://127.0.0.1:8300")))
        self.assertTrue(app.ws_allowed(WS("localhost:8300")))
        self.assertFalse(app.ws_allowed(WS("evil.example:8300", "http://evil.example:8300")))
        self.assertFalse(app.ws_allowed(WS("127.0.0.1:8300", "http://evil.example")))


if __name__ == "__main__":
    unittest.main()
