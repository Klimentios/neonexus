"""Connect AI (PRODUCT.md M5): bring any model into the room from the browser.

Three ways in, all optional and off until the user adds them:
  * Subscription CLIs (Claude Code, Codex, Gemini CLI, Qwen Code, Copilot CLI):
    detect, install with one click (npm), sign in inside their own terminal.
  * API providers (OpenAI, Anthropic, OpenRouter, Groq, DeepSeek, Mistral, Gemini,
    xAI or any OpenAI-compatible URL) and local servers (Ollama, LM Studio,
    llama.cpp, vLLM, a remote GPU box): become a room agent through the existing
    wrapper_api.py engine, configured in config.local.toml.
  * Other apps over MCP (Claude Desktop, Cursor, ...): a ready config snippet for
    council_bridge.py.

Keys live in data/secrets.json (mode 600 from creation, data/ is gitignored) and
are only ever sent to the base URL the agent was saved with: a probe with a saved
key always uses the stored URL, and changing an agent's base URL without typing a
new key drops the old key. They never appear in config.local.toml, the browser
after saving, logs or the room. Every read-modify-write of secrets.json and
config.local.toml runs under one module lock.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import uuid
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).parent
_NAME = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
# One lock for every read-modify-write of secrets.json and config.local.toml
# (re-entrant: add() holds it across read, write and the secret update).
_LOCK = threading.RLock()

CLIS = [
    {"id": "claude", "label": "Claude Code", "vendor": "Anthropic", "command": "claude",
     "npm": "@anthropic-ai/claude-code", "plan": "Claude Pro / Max / Team"},
    {"id": "codex", "label": "Codex CLI", "vendor": "OpenAI", "command": "codex",
     "npm": "@openai/codex", "plan": "ChatGPT Plus / Pro / Team"},
    {"id": "gemini-cli", "label": "Gemini CLI", "vendor": "Google", "command": "gemini",
     "npm": "@google/gemini-cli", "plan": "Google account / AI Pro"},
    {"id": "agy", "label": "Antigravity CLI", "vendor": "Google", "command": "agy",
     "npm": "", "plan": "Google AI Pro / Ultra"},
    {"id": "qwen", "label": "Qwen Code", "vendor": "Alibaba", "command": "qwen",
     "npm": "@qwen-code/qwen-code", "plan": "Qwen account"},
    {"id": "copilot", "label": "Copilot CLI", "vendor": "GitHub", "command": "copilot",
     "npm": "@github/copilot", "plan": "GitHub Copilot"},
]

PROVIDERS = [
    {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "key": True},
    {"id": "anthropic", "label": "Anthropic", "base_url": "https://api.anthropic.com/v1", "key": True},
    {"id": "openrouter", "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "key": True},
    {"id": "gemini", "label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "key": True},
    {"id": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1", "key": True},
    {"id": "deepseek", "label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "key": True},
    {"id": "mistral", "label": "Mistral", "base_url": "https://api.mistral.ai/v1", "key": True},
    {"id": "xai", "label": "xAI", "base_url": "https://api.x.ai/v1", "key": True},
    {"id": "custom", "label": "Other (OpenAI-compatible)", "base_url": "", "key": True},
]

LOCAL = [
    {"id": "ollama", "label": "Ollama", "base_url": "http://localhost:11434/v1"},
    {"id": "lmstudio", "label": "LM Studio", "base_url": "http://localhost:1234/v1"},
    {"id": "llamacpp", "label": "llama.cpp server", "base_url": "http://localhost:8080/v1"},
    {"id": "vllm", "label": "vLLM", "base_url": "http://localhost:8000/v1"},
    {"id": "remote", "label": "Remote GPU server", "base_url": ""},
]

COLORS = ["#7c5cff", "#0ea5e9", "#f97316", "#10b981", "#e11d48", "#a855f7", "#14b8a6", "#eab308"]


# ---------------- secrets ----------------

def _secrets_path(data_dir: Path) -> Path:
    return data_dir / "secrets.json"


def read_secret(data_dir: Path, name: str) -> str:
    try:
        return json.loads(_secrets_path(data_dir).read_text("utf-8")).get(name, "")
    except (OSError, json.JSONDecodeError):
        return ""


def _atomic_write(path: Path, text: str, mode: int = 0o644):
    """Write a sibling temp file created with `mode` (never wider), then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_secret(data_dir: Path, name: str, value: str | None):
    path = _secrets_path(data_dir)
    with _LOCK:
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        if value:
            data[name] = value
        else:
            data.pop(name, None)
        _atomic_write(path, json.dumps(data), 0o600)


# ---------------- config.local.toml ----------------

def _toml_key(k) -> str:
    k = str(k)
    return k if _BARE_KEY.fullmatch(k) else json.dumps(k, ensure_ascii=False)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(x)}" for k, x in v.items()) + " }"
    if hasattr(v, "isoformat"):  # tomllib datetime / date / time
        return v.isoformat()
    return json.dumps(str(v), ensure_ascii=False)  # JSON string escaping is valid TOML


def _is_table_array(v) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v)


def _toml_table(path: list[str], table: dict, out: list[str], *, array: bool = False):
    """Emit one table: its plain keys first, then sub-tables and arrays of tables."""
    header = ".".join(_toml_key(p) for p in path)
    plain = {k: v for k, v in table.items() if not isinstance(v, dict) and not _is_table_array(v)}
    nested = {k: v for k, v in table.items() if k not in plain}
    if array:
        out.append(f"[[{header}]]")
    elif path and (plain or not nested):
        out.append(f"[{header}]")
    out += [f"{_toml_key(k)} = {_toml_value(v)}" for k, v in plain.items()]
    if plain or array:
        out.append("")
    for k, v in nested.items():
        if isinstance(v, dict):
            _toml_table(path + [str(k)], v, out)
        else:
            for item in v:
                _toml_table(path + [str(k)], item, out, array=True)


def _read_local(root: Path) -> dict:
    try:
        return tomllib.loads((root / "config.local.toml").read_text("utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _write_local(root: Path, local: dict):
    """Serialize the whole parsed config back to TOML (lists, nested tables kept)."""
    out = ["# config.local.toml — written by NEONEXUS Connect AI. Agents added in the browser.",
           "# API keys are NOT here: they live in data/secrets.json.", ""]
    _toml_table([], local, out)
    with _LOCK:
        _atomic_write(root / "config.local.toml", "\n".join(out).rstrip("\n") + "\n")


def probe_request(data_dir: Path, body: dict) -> tuple[str, str]:
    """Pick (base_url, key) for a probe. A saved key only ever goes to its stored URL."""
    url = str(body.get("base_url") or "").strip().rstrip("/")
    key = str(body.get("key") or "")
    if key:
        return url, key
    name = str(body.get("name") or "")
    if not name:
        return url, ""
    stored = str(((_read_local(ROOT).get("agents") or {}).get(name) or {}).get("base_url") or "").rstrip("/")
    secret = read_secret(data_dir, name)
    if not stored or (url and url != stored):
        return url, ""  # an unsaved or edited URL is probed without the saved key
    return stored, secret


# ---------------- probing an endpoint ----------------

def probe(base_url: str, key: str = "", timeout: float = 8.0) -> dict:
    """GET {base}/models: is it reachable, does the key work, which models exist."""
    base = base_url.rstrip("/")
    if not re.match(r"^https?://", base):
        return {"ok": False, "error": "base URL must start with http:// or https://"}
    req = urllib.request.Request(f"{base}/models", headers={"Accept": "application/json"})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
        if "anthropic.com" in base:
            req.add_header("x-api-key", key)
            req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        msg = {401: "the key was refused (401)", 403: "access denied (403)", 404: "no /models here (404)"}.get(e.code, f"HTTP {e.code}")
        return {"ok": False, "error": msg}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        return {"ok": False, "error": f"not reachable: {reason}"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "the answer is not JSON"}
    items = data.get("data") if isinstance(data, dict) else data
    ids = sorted({str(m.get("id")) for m in (items or []) if isinstance(m, dict) and m.get("id")})
    return {"ok": True, "models": ids[:400]}


# ---------------- the service ----------------

class Connect:
    def __init__(self, data_dir: str, config: dict, registry=None):
        self.data_dir = Path(data_dir)
        self.config = config
        self.registry = registry
        self.installs: dict[str, dict] = {}

    # --- running API agents ---
    def _session(self, name: str) -> str:
        return f"council-{name}"

    def running(self, name: str) -> bool:
        if sys.platform == "win32":
            return bool(self.registry and name in self.registry.get_all())
        r = subprocess.run(["tmux", "-L", "council-wrappers", "has-session", "-t", self._session(name)],
                           capture_output=True, check=False)
        return r.returncode == 0

    def start(self, name: str) -> str:
        if self.running(name):
            return "already running"
        cmd = [sys.executable, str(ROOT / "wrapper_api.py"), name]
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(cmd, cwd=str(ROOT), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "started"
        env = {**os.environ}
        env.pop("TMUX", None)
        r = subprocess.run(["tmux", "-L", "council-wrappers", "new-session", "-d", "-s", self._session(name),
                            " ".join(shlex.quote(c) for c in cmd)], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, check=False)
        return "started" if r.returncode == 0 else f"could not start: {r.stderr.strip()[:200]}"

    def stop(self, name: str):
        if sys.platform != "win32":
            subprocess.run(["tmux", "-L", "council-wrappers", "kill-session", "-t", self._session(name)],
                           capture_output=True, check=False)
        if self.registry and name in self.registry.get_all():
            try:
                self.registry.deregister(name)
            except Exception:
                pass

    def autostart(self):
        for name, cfg in (_read_local(ROOT).get("agents") or {}).items():
            if cfg.get("type") == "api" and cfg.get("enabled", True):
                self.start(name)

    # --- catalog ---
    def api_agents(self) -> list[dict]:
        out = []
        for name, cfg in (_read_local(ROOT).get("agents") or {}).items():
            if cfg.get("type") != "api":
                continue
            out.append({"name": name, "label": cfg.get("label", name), "base_url": cfg.get("base_url", ""),
                        "model": cfg.get("model", ""), "color": cfg.get("color", "#888"),
                        "kind": cfg.get("kind", "api"), "provider": cfg.get("provider", ""),
                        "has_key": bool(read_secret(self.data_dir, name)),
                        "running": self.running(name),
                        "online": bool(self.registry and name in self.registry.get_all())})
        return out

    def catalog(self) -> dict:
        team_cmds = {str(c.get("command", "")) for c in self.config.get("agents", {}).values()}
        clis = []
        for c in CLIS:
            path = shutil.which(c["command"])
            clis.append({**c, "installed": bool(path), "in_team": bool(path) and c["command"] in team_cmds,
                         "install": self.installs.get(c["id"], {}).get("state", "")})
        port = self.config.get("mcp", {}).get("http_port", 8200)
        return {
            "platform": {"darwin": "mac", "win32": "windows"}.get(sys.platform, "linux"),
            "npm": bool(shutil.which("npm")),
            "clis": clis, "providers": PROVIDERS, "local": LOCAL, "agents": self.api_agents(),
            "mcp": {
                "url": f"http://127.0.0.1:{port}/mcp",
                "bridge": {"command": sys.executable, "args": [str(ROOT / "council_bridge.py")],
                           "env": {"COUNCIL_SENDER": "app-myapp"}},
            },
        }

    # --- add an installed CLI to the team ---
    def add_cli(self, cli_id: str) -> dict | str:
        c = next((x for x in CLIS if x["id"] == cli_id), None)
        if not c:
            return "unknown CLI"
        if not shutil.which(c["command"]):
            return f"{c['label']} is not installed"
        team = self.config.setdefault("agents", {})
        if any(str(a.get("command")) == c["command"] for a in team.values() if isinstance(a, dict)):
            return f"{c['label']} is already in the team"
        name = re.sub(r"[^a-z0-9]", "", cli_id.lower())[:24] or "agent"
        while name in team:
            name += "x"
        entry = {"command": c["command"], "cwd": "{workspace}", "label": c["label"],
                 "color": COLORS[len(team) % len(COLORS)]}
        with _LOCK:
            local = _read_local(ROOT)
            local.setdefault("agents", {})[name] = entry
            _write_local(ROOT, local)
        team[name] = {**entry, "cwd": os.path.expanduser(str(self.config.get("paths", {}).get("workspace", "~")))}
        # start it the same way every agent starts (its own terminal + wrapper)
        env = {**os.environ, "COUNCIL_NO_OPEN": "1", "TMUX_TMPDIR": str(ROOT / "data" / "tmux")}
        env.pop("TMUX", None)
        if sys.platform != "win32" and (ROOT / "council.sh").exists():
            subprocess.Popen(["/bin/sh", str(ROOT / "council.sh"), "start-one", name], cwd=str(ROOT), env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return {"ok": True, "name": name, "label": c["label"]}

    # --- add / remove ---
    def add(self, body: dict) -> dict | str:
        name = str(body.get("name", "")).strip().lower()
        if not _NAME.fullmatch(name):
            return "name: 2-24 lowercase letters, digits or dashes, starting with a letter"
        if name in self.config.get("agents", {}) and self.config["agents"][name].get("type") != "api":
            return f"{name} is already a CLI agent; pick another name"
        base_url = str(body.get("base_url", "")).strip().rstrip("/")
        if not re.match(r"^https?://[^\s]+$", base_url):
            return "base URL must start with http:// or https://"
        model = str(body.get("model", "")).strip()
        if not model or len(model) > 120:
            return "pick a model"
        label = str(body.get("label") or model).strip()[:40]
        key = str(body.get("key") or "")
        color = str(body.get("color") or "")
        if not _COLOR.fullmatch(color):
            used = {a["color"] for a in self.api_agents()}
            color = next((c for c in COLORS if c not in used), COLORS[0])
        cfg = {"type": "api", "kind": body.get("kind", "api") if body.get("kind") in ("api", "local") else "api",
               "provider": str(body.get("provider", ""))[:24], "base_url": base_url, "model": model,
               "label": label, "color": color, "api_key_secret": name, "context_messages": 20, "enabled": True}
        prompt = str(body.get("system_prompt") or "").strip()
        if prompt:
            cfg["system_prompt"] = prompt[:4000]
        key_dropped = False
        with _LOCK:
            local = _read_local(ROOT)
            old = (local.get("agents") or {}).get(name) or {}
            moved = bool(old) and str(old.get("base_url") or "").rstrip("/") != base_url
            local.setdefault("agents", {})[name] = cfg
            _write_local(ROOT, local)
            if key:
                _write_secret(self.data_dir, name, key)
            elif moved and read_secret(self.data_dir, name):
                # The saved key belongs to the old URL: never send it elsewhere.
                _write_secret(self.data_dir, name, None)
                key_dropped = True
        self.config.setdefault("agents", {})[name] = cfg
        if self.registry:
            self.registry.seed({name: cfg})
        self.stop(name)  # restart with the new settings
        time.sleep(0.3)
        state = self.start(name)
        result = {"name": name, "label": label, "state": state}
        if key_dropped:
            result["key_dropped"] = True
            result["note"] = "base URL changed: the saved key was removed, enter it again"
        return result

    def remove(self, name: str) -> str:
        if name not in (_read_local(ROOT).get("agents") or {}):
            return f"no connected model {name}"
        self.stop(name)
        with _LOCK:
            local = _read_local(ROOT)
            (local.get("agents") or {}).pop(name, None)
            _write_local(ROOT, local)
            _write_secret(self.data_dir, name, None)
        cfg = self.config.get("agents", {}).get(name)
        if cfg and cfg.get("type") == "api":
            cfg["enabled"] = False
        return "removed"

    # --- installing a CLI ---
    def install(self, cli_id: str) -> str:
        c = next((x for x in CLIS if x["id"] == cli_id), None)
        if not c or not c["npm"]:
            return "this CLI has no one-click install; use its own installer"
        npm = shutil.which("npm")
        if not npm:
            return "npm is not installed: install Node.js (nodejs.org) first"
        if self.installs.get(cli_id, {}).get("state") == "running":
            return "already installing"
        log = self.data_dir / f"install-{cli_id}.log"
        self.installs[cli_id] = {"state": "running", "log": str(log)}

        def run():
            with open(log, "w", encoding="utf-8") as f:
                p = subprocess.run([npm, "install", "-g", c["npm"]], stdout=f, stderr=subprocess.STDOUT, check=False)
            self.installs[cli_id]["state"] = "done" if p.returncode == 0 else "failed"
        threading.Thread(target=run, daemon=True).start()
        return "installing"

    def install_log(self, cli_id: str) -> str:
        info = self.installs.get(cli_id)
        if not info:
            return ""
        try:
            return Path(info["log"]).read_text("utf-8", "replace")[-4000:]
        except OSError:
            return ""


connect: Connect | None = None


def configure(data_dir: str, config: dict, registry=None, autostart: bool = True) -> Connect:
    global connect
    connect = Connect(data_dir, config, registry)
    if autostart:
        threading.Thread(target=connect.autostart, daemon=True).start()
    return connect


# ---------------- HTTP (the browser = the user) ----------------

router = APIRouter()


def _err(msg: str, code: int = 400):
    return JSONResponse({"error": msg}, status_code=code)


@router.get("/api/connect")
async def get_catalog():
    import asyncio
    return await asyncio.to_thread(connect.catalog)


@router.post("/api/connect/probe")
async def post_probe(request: Request):
    """{"base_url", "key"?, "name"?}: test an endpoint. With `name` and no key, the
    saved key is used only against that agent's STORED base URL."""
    import asyncio
    b = await request.json()
    if not isinstance(b, dict):
        return _err("expected a JSON object")
    base_url, key = await asyncio.to_thread(probe_request, connect.data_dir, b)
    return await asyncio.to_thread(probe, base_url, key)


@router.post("/api/connect/agents")
async def post_agent(request: Request):
    import asyncio
    r = await asyncio.to_thread(connect.add, await request.json())
    return _err(r) if isinstance(r, str) else r


@router.delete("/api/connect/agents/{name}")
async def delete_agent(name: str):
    import asyncio
    r = await asyncio.to_thread(connect.remove, name)
    return {"result": r} if r == "removed" else _err(r, 404)


@router.post("/api/connect/agents/{name}/restart")
async def restart_agent(name: str):
    import asyncio
    await asyncio.to_thread(connect.stop, name)
    return {"result": await asyncio.to_thread(connect.start, name)}


@router.post("/api/connect/team/{cli_id}")
async def add_cli_to_team(cli_id: str):
    """One click: an installed CLI that has no agent yet becomes a team member and starts."""
    import asyncio
    r = await asyncio.to_thread(connect.add_cli, cli_id)
    return r if isinstance(r, dict) else _err(r)


@router.post("/api/connect/install/{cli_id}")
async def install_cli(cli_id: str):
    r = connect.install(cli_id)
    return {"result": r} if r == "installing" else _err(r)


@router.get("/api/connect/install/{cli_id}")
async def install_status(cli_id: str):
    return {"state": connect.installs.get(cli_id, {}).get("state", ""), "log": connect.install_log(cli_id)}
