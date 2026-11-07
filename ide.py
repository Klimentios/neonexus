"""Full VS Code inside the Code tab: open-source code-server (MIT, coder/code-server),
fetched once into data/code-server/ and run on 127.0.0.1 — no licence prompt, nothing
for the user to install or watch.

  * pinned release + sha256 from the GitHub release (a two-week-old version, not the newest)
  * VS Code workspace trust stays ON and automatic tasks are off, so a cloned repo
    cannot run its .vscode tasks or extensions' code on open
  * password auth: a random password in data/ (0600 from creation); the room page logs the iframe in through
    a one-shot nonce (/ide/login), so other local pages can't use the editor
  * while it is being fetched / started, the Code tab shows the built-in Monaco editor
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

PORT = 8444
VERSION = "4.143.1"
SHA256 = {
    "macos-arm64": "940bb5ecd567187336ed3608c2404e21e37528465aaddb4d6f5b514d930bd7db",
    "macos-amd64": "0c77b28570d67c729bf75e57dc92bb51af0b4c683f89e1e756c168d30dcc0d63",
    "linux-amd64": "614877cf71005f14ea252bd2d9b1c12237cf7d73681ef150f0dff7f13849fdb5",
    "linux-arm64": "51481a891754dc2585b86d007aec24ac675453fc5ef6cfa346c4462449277384",
    "windows-amd64": "a480ccbc368336370baaa16336143e1d8bb9868e66edb2ea3f076ebf0527080a",
}


def target() -> str | None:
    os_ = {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform)
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "amd64": "amd64"}.get(platform.machine().lower())
    t = f"{os_}-{arch}"
    return t if t in SHA256 else None


class IDE:
    def __init__(self, data_dir: str, folder: str):
        self.data = Path(data_dir)
        self.base = self.data / "code-server"
        self.home = self.base / VERSION
        self.folder = folder
        self.proc: subprocess.Popen | None = None
        self.phase = "idle"   # idle | download | extract | starting | ready | error
        self.progress = 0
        self.error = ""
        self.nonces: dict[str, float] = {}
        self._lock = threading.Lock()
        self._pw_lock = threading.Lock()

    # --- secrets ---
    def password(self) -> str:
        p = self.base / "password"
        with self._pw_lock:
            try:
                pw = p.read_text("utf-8").strip()
                if pw:
                    return pw
            except OSError:
                pass
            pw = secrets.token_urlsafe(24)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f".password.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(pw.encode("utf-8"))
                os.replace(tmp, p)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            return pw

    def nonce(self) -> str:
        now = time.time()
        self.nonces = {k: v for k, v in self.nonces.items() if v > now}
        n = secrets.token_urlsafe(18)
        self.nonces[n] = now + 60
        return n

    def take_nonce(self, n: str) -> bool:
        return self.nonces.pop(n, 0) > time.time()

    # --- install ---
    def entry(self) -> list[str] | None:
        node = self.home / "lib" / ("node.exe" if sys.platform == "win32" else "node")
        js = self.home / "out" / "node" / "entry.js"
        return [str(node), str(js)] if node.exists() and js.exists() else None

    def _download(self):
        t = target()
        if not t:
            raise RuntimeError(f"no code-server build for {sys.platform}/{platform.machine()}")
        name = f"code-server-{VERSION}-{t}"
        url = f"https://github.com/coder/code-server/releases/download/v{VERSION}/{name}.tar.gz"
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self.base / f"{name}.tar.gz.part"
        self.phase, self.progress = "download", 0
        h = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if total:
                    self.progress = int(got * 100 / total)
        if h.hexdigest() != SHA256[t]:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("code-server download checksum mismatch")
        self.phase = "extract"
        out = self.base / f"{VERSION}.part"
        shutil.rmtree(out, ignore_errors=True)
        with tarfile.open(tmp) as tf:
            tf.extractall(out, filter="tar")
        inner = out / name
        shutil.rmtree(self.home, ignore_errors=True)
        (inner if inner.is_dir() else out).rename(self.home)
        shutil.rmtree(out, ignore_errors=True)
        tmp.unlink(missing_ok=True)

    # --- run ---
    def _port_up(self) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    def _pid(self) -> int:
        """Our code-server, also one started before the room restarted (it keeps running).

        A pid from the pid file counts only while that process is still a code-server:
        pids are reused, and stop() must never kill an unrelated program. On Windows
        only the process this room started is trusted."""
        if self.proc and self.proc.poll() is None:
            return self.proc.pid
        if sys.platform == "win32":
            return 0
        try:
            pid = int((self.base / "pid").read_text().strip())
            if pid <= 1:
                return 0
            os.kill(pid, 0)
        except (OSError, ValueError):
            return 0
        return pid if _is_code_server(pid) else 0

    def running(self) -> bool:
        return bool(self._pid()) and self._port_up()

    def _settings(self):
        """Quiet defaults: no welcome page, no telemetry, light theme, and no VS Code's own
        AI chat (the room's agents are the AI). Workspace trust stays on and automatic
        tasks are off. The user's own changes stay, except the trust switch-off that
        older versions of this file wrote (removed when it is still false)."""
        user = self.base / "user-data" / "User"
        user.mkdir(parents=True, exist_ok=True)
        s = user / "settings.json"
        try:
            cur = json.loads(s.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            cur = {}
        defaults = {
            "workbench.startupEditor": "none",
            "workbench.colorTheme": "Light Modern",
            "task.allowAutomaticTasks": "off",
            "telemetry.telemetryLevel": "off",
            "update.mode": "none",
            "extensions.autoCheckUpdates": False,
            "chat.disableAIFeatures": True,
            "workbench.secondarySideBar.defaultVisibility": "hidden",
        }
        if not isinstance(cur, dict):
            cur = {}
        dropped = cur.get("security.workspace.trust.enabled") is False
        if dropped:
            cur.pop("security.workspace.trust.enabled")
        if dropped or any(k not in cur for k in defaults):
            s.write_text(json.dumps({**defaults, **cur}, indent=2), "utf-8")

    # VS Code renamed its default themes ("Default Light Modern" → "Light Modern"); both count as ours
    LIGHT = ("Light Modern", "Default Light Modern", "Light+", "Default Light+")
    DARK = ("Dark Modern", "Default Dark Modern", "Dark+", "Default Dark+")
    THEMES = (LIGHT[0], DARK[0])

    def set_theme(self, dark: bool) -> str:
        """Follow NEONEXUS's light / dark skin — unless the user picked another VS Code theme."""
        s = self.base / "user-data" / "User" / "settings.json"
        try:
            cur = json.loads(s.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            cur = None
        if not isinstance(cur, dict):
            self._settings()
            try:
                cur = json.loads(s.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                return "no settings"
        want = self.THEMES[1] if dark else self.THEMES[0]
        if cur.get("workbench.colorTheme", self.THEMES[0]) not in self.LIGHT + self.DARK:
            return "user theme kept"
        if cur.get("workbench.colorTheme") != want:
            cur["workbench.colorTheme"] = want
            tmp = s.with_suffix(".tmp")
            tmp.write_text(json.dumps(cur, indent=2), "utf-8")
            tmp.replace(s)  # VS Code picks the change up live
        return want

    def _run(self):
        try:
            if not self.entry():
                self._download()
            cmd = self.entry()
            if not cmd:
                raise RuntimeError("code-server files are incomplete")
            self.phase = "starting"
            self._settings()
            env = {**os.environ, "PASSWORD": self.password()}
            env.pop("HASHED_PASSWORD", None)
            (self.data / "logs").mkdir(parents=True, exist_ok=True)
            log = open(self.data / "logs" / "code-server.log", "a", encoding="utf-8")
            kw = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL, "env": env}
            if sys.platform == "win32":
                kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                kw["start_new_session"] = True
            self.proc = subprocess.Popen(cmd + [
                "--config", str(self.base / "config.yaml"),
                "--bind-addr", f"127.0.0.1:{PORT}", "--auth", "password",
                "--user-data-dir", str(self.base / "user-data"),
                "--extensions-dir", str(self.base / "extensions"),
                "--disable-telemetry", "--disable-update-check",
                "--disable-getting-started-override", "--ignore-last-opened", self.folder,
            ], **kw)
            (self.base / "pid").write_text(str(self.proc.pid))
            for _ in range(120):
                if self.proc.poll() is not None:
                    raise RuntimeError("code-server exited; see data/logs/code-server.log")
                if self._port_up():
                    self.phase = "ready"
                    return
                time.sleep(0.5)
            raise RuntimeError("code-server did not start in 60 s")
        except Exception as e:  # shown as a small note; the built-in editor keeps working
            self.phase, self.error = "error", str(e)[:300]

    def ensure(self):
        with self._lock:
            if self.phase in ("download", "extract", "starting"):
                return
            if self.running():
                self.phase = "ready"
                return
            if self._port_up():
                self.phase, self.error = "error", f"port {PORT} is used by another program"
                return
            self.phase, self.error = "starting", ""
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        """Stop only our code-server: self.proc, or a verified code-server from the pid file."""
        pid = self._pid()
        if pid:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
                else:
                    try:
                        os.killpg(pid, 15)  # started with start_new_session: pid is the group
                    except (OSError, ProcessLookupError):
                        os.kill(pid, 15)
            except (OSError, ProcessLookupError):
                pass
            try:
                (self.base / "pid").unlink()
            except OSError:
                pass
        self.proc, self.phase = None, "idle"

    def status(self) -> dict:
        if self.phase in ("idle", "ready"):
            self.phase = "ready" if self.running() else "idle"
        return {"phase": self.phase, "progress": self.progress, "error": self.error,
                "installed": bool(self.entry()), "folder": self.folder,
                "login": f"/ide/login?n={self.nonce()}" if self.phase == "ready" else ""}

    def login_page(self, n: str, sub: str = "") -> HTMLResponse:
        if not self.take_nonce(n) or self.phase != "ready":
            return HTMLResponse("expired", status_code=403)
        folder = Path(self.folder).resolve()
        if sub:  # Code mode opens VS Code on the task's own folder inside the workspace
            cand = (folder / sub).resolve()
            if cand.is_relative_to(folder) and cand.is_dir():
                folder = cand
        to = "/?" + urllib.parse.urlencode({"folder": str(folder)})
        action = f"http://127.0.0.1:{PORT}/login?" + urllib.parse.urlencode({"to": to})
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><meta name=referrer content=no-referrer>"
            "<body style='background:#fff'>"
            f"<form id=f method=post action='{html.escape(action)}'>"
            f"<input type=hidden name=password value='{html.escape(self.password())}'></form>"
            "<script>document.getElementById('f').submit()</script>",
            headers={"Cache-Control": "no-store"})


def _is_code_server(pid: int) -> bool:
    """True when the process' command line names code-server (ps on macOS/Linux)."""
    try:
        r = subprocess.run(["ps", "-p", str(int(pid)), "-o", "command="],
                           capture_output=True, text=True, timeout=5, check=False)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "code-server" in r.stdout


ide: IDE | None = None


def configure(data_dir: str, folder: str, autostart: bool = True) -> IDE:
    """Warm it up with the room when it is already installed, so the tab opens instantly."""
    global ide
    ide = IDE(data_dir, folder)
    if autostart and ide.entry():
        ide.ensure()
    return ide


router = APIRouter()


# status()/ensure()/stop() block (health check over urlopen, ps, file reads): keep
# them off the event loop.
@router.get("/api/ide")
async def get_ide():
    return await asyncio.to_thread(ide.status)


@router.post("/api/ide/start")
async def start_ide():
    await asyncio.to_thread(ide.ensure)
    return await asyncio.to_thread(ide.status)


@router.post("/api/ide/theme")
async def ide_theme(request: Request):
    b = await request.json()
    return {"theme": await asyncio.to_thread(ide.set_theme, bool((b or {}).get("dark")) if isinstance(b, dict) else False)}


@router.get("/ide/login")
async def ide_login(n: str = "", sub: str = ""):
    return await asyncio.to_thread(ide.login_page, n, sub)


@router.post("/api/ide/stop")
async def stop_ide():
    await asyncio.to_thread(ide.stop)
    return await asyncio.to_thread(ide.status)
