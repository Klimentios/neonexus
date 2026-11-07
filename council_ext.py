"""Council extensions — channel missions, agent personas, decision log.

Kept in one module beside the upstream stores so merges from upstream
agentchattr stay small. app.configure() creates the store and calls
`attach_store_hook`; the HTTP routes live in `router` (included by app.py);
the MCP tools live in mcp_bridge.py and call into the store.

Decisions are the project memory: every one is appended to
data/decisions.jsonl and mirrored to <workspace>/.council/DECISIONS.md so any
agent (or a fresh session of any model) can read them as a plain file.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

MAX_MISSION_TITLE = 120
MAX_MISSION_BODY = 1000
MAX_DECISION_TEXT = 1000
MAX_PERSONA_FIELD = 200
MAX_AGENT_INSTRUCTIONS = 1800

# Shared capability, distinct working styles. These guide behavior; they do not
# grant tools or model access beyond the actual CLI session.
COMMON_AGENT_INSTRUCTIONS = (
    "Reply in the language the user writes in. You are a capable generalist; your specialty is a comparative "
    "strength, not an exclusive power or a claim about hidden model training. Work as one team. "
    "For a substantial task, propose an owner and one reviewer with complementary strengths. "
    "Independently suggest a useful alternative when needed, challenge ideas with evidence rather "
    "than attacking agents, then converge on one decision and execute it. Ask another agent a "
    "specific question when their expertise helps; avoid mention loops, duplicate work and "
    "conflicting edits. The coordinator tracks the plan and unresolved questions; the user has "
    "final authority. Inspect the real project, verify results, state uncertainty and tool limits, "
    "and never claim an action you did not perform. Respect project boundaries and approvals."
)
AGENT_STYLES = {
    "claude": "Your character is the calm systems integrator: connect intent, architecture and writing; surface dependencies, decide who should own a task, and invite focused review. Do not confuse coordination with final authority.",
    "codex": "Your character is the pragmatic builder: inspect code, reproduce failures, make precise changes and verify runtime behavior. Challenge elegant plans that lack an executable path.",
    "gemini": "Your character is the curious explorer: compare alternatives, inspect visual or multimodal evidence when tools allow, and expose blind spots. Turn exploration into a concrete recommendation.",
    "claudechat": "Your character is the thoughtful critic: clarify intent, stress-test assumptions and improve explanations. As a chat partner, do not claim file edits or direct system inspection you did not perform.",
    "gptchat": "Your character is the structured analyst: separate facts, inference and open questions; compare tradeoffs and test the team's logic. As a chat partner, do not claim unavailable tools or edits.",
    "geminichat": "Your character is the imaginative product scout: propose visual and workflow alternatives, then test them against usability and constraints. As a chat partner, do not claim unavailable tools or edits.",
}


def agent_instructions(agent: str, council_store=None) -> str:
    base = re.sub(r"-\d+$", "", agent)
    saved = (council_store.persona(agent).get("instructions", "") if council_store else "")
    if not saved and council_store and base != agent:
        saved = council_store.persona(base).get("instructions", "")
    return saved or f"{COMMON_AGENT_INSTRUCTIONS} {AGENT_STYLES.get(base, '')}".strip()

# "DECISION: ...", "**Decision:** ...", "РЕШЕНИЕ: ..." at the start of a message
DECISION_RE = re.compile(r"^\s*\**\s*(decision|решение)\s*\**\s*[:：]\s*\**\s*", re.IGNORECASE)


def _atomic_write(path: Path, text: str):
    """Temp file next to the target, then os.replace: a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(text, "utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class CouncilStore:
    def __init__(self, data_dir: str, workspace: str | None = None):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "council.json"
        self._decisions_path = self._dir / "decisions.jsonl"
        self._workspace = Path(workspace) if workspace else None
        self._lock = threading.Lock()
        self._callbacks: list = []  # (kind, data) on any change
        self._missions: dict[str, dict] = {}
        self._personas: dict[str, dict] = {}
        self._decisions: list[dict] = []
        self._load()

    # --- persistence ---

    def _load(self):
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text("utf-8"))
                self._missions = raw.get("missions", {})
                self._personas = raw.get("personas", {})
            except (json.JSONDecodeError, AttributeError):
                pass
        if self._decisions_path.exists():
            for line in self._decisions_path.read_text("utf-8").splitlines():
                try:
                    self._decisions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def _save(self):
        _atomic_write(self._path, json.dumps(
            {"missions": self._missions, "personas": self._personas},
            indent=2, ensure_ascii=False) + "\n")

    def _save_decisions(self):
        self._decisions_path.write_text(
            "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in self._decisions), "utf-8")
        self._mirror_decisions()

    def _mirror_decisions(self):
        """Write the human/agent-readable project memory file into the workspace."""
        if not self._workspace:
            return
        try:
            out = self._workspace / ".council" / "DECISIONS.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            lines = ["# Decisions", "",
                     "Project memory kept by Council. Newest last. Do not edit by hand.", ""]
            for d in self._decisions:
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(d["created_at"]))
                lines.append(f"- [{when}] #{d['channel']} — {d['author']}: {d['text']}")
            out.write_text("\n".join(lines) + "\n", "utf-8")
        except OSError:
            pass

    def on_change(self, callback):
        """Register callback(kind, data). kind: mission, persona, decision, decision_delete."""
        self._callbacks.append(callback)

    def _fire(self, kind: str, data: dict):
        for cb in self._callbacks:
            try:
                cb(kind, data)
            except Exception:
                pass

    # --- missions (one goal per channel) ---

    def missions(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._missions.items()}

    def mission(self, channel: str) -> dict | None:
        with self._lock:
            m = self._missions.get(channel)
            return dict(m) if m else None

    def set_mission(self, channel: str, title: str, body: str = "", due: str = "") -> dict:
        from jobs import _clean_due
        with self._lock:
            m = {
                "channel": channel,
                "title": title.strip()[:MAX_MISSION_TITLE],
                "body": body.strip()[:MAX_MISSION_BODY],
                "due": _clean_due(due) or "",
                "updated_at": time.time(),
            }
            self._missions[channel] = m
            self._save()
        self._fire("mission", m)
        return m

    def clear_mission(self, channel: str) -> bool:
        with self._lock:
            if self._missions.pop(channel, None) is None:
                return False
            self._save()
        self._fire("mission", {"channel": channel, "deleted": True})
        return True

    # --- personas (Architect / Researcher / Coder / Critic on top of an agent instance) ---

    def personas(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._personas.items()}

    def persona(self, agent: str) -> dict:
        with self._lock:
            return dict(self._personas.get(agent, {}))

    def set_persona(self, agent: str, fields: dict) -> dict:
        with self._lock:
            p = dict(self._personas.get(agent, {}))
            for key in ("title", "avatar", "color", "description", "instructions"):
                if key in fields:
                    limit = MAX_AGENT_INSTRUCTIONS if key == "instructions" else MAX_PERSONA_FIELD
                    p[key] = str(fields[key] or "").strip()[:limit]
            p["agent"] = agent
            p["updated_at"] = time.time()
            self._personas[agent] = p
            self._save()
        self._fire("persona", p)
        return p

    def clear_persona(self, agent: str) -> bool:
        with self._lock:
            if self._personas.pop(agent, None) is None:
                return False
            self._save()
        self._fire("persona", {"agent": agent, "deleted": True})
        return True

    # --- decisions (project memory) ---

    def decisions(self, channel: str = "", limit: int = 100) -> list[dict]:
        with self._lock:
            items = [d for d in self._decisions if not channel or d["channel"] == channel]
        return items[-limit:] if limit > 0 else items

    def add_decision(self, text: str, author: str, channel: str = "general",
                     msg_id: int | None = None) -> dict | None:
        text = text.strip()[:MAX_DECISION_TEXT]
        if not text:
            return None
        with self._lock:
            if msg_id is not None and any(d.get("msg_id") == msg_id for d in self._decisions):
                return None
            next_id = max((d["id"] for d in self._decisions), default=0) + 1
            d = {
                "id": next_id,
                "uid": str(uuid.uuid4()),
                "text": text,
                "author": author,
                "channel": channel or "general",
                "msg_id": msg_id,
                "created_at": time.time(),
            }
            self._decisions.append(d)
            self._save_decisions()
        self._fire("decision", d)
        return d

    def delete_decision(self, decision_id: int) -> bool:
        with self._lock:
            before = len(self._decisions)
            self._decisions = [d for d in self._decisions if d["id"] != decision_id]
            if len(self._decisions) == before:
                return False
            self._save_decisions()
        self._fire("decision_delete", {"id": decision_id})
        return True

    def capture_from_message(self, msg: dict):
        """Record chat messages that start with DECISION: / РЕШЕНИЕ: as decisions."""
        if msg.get("type", "chat") != "chat":
            return
        text = msg.get("text", "")
        m = DECISION_RE.match(text)
        if not m:
            return
        self.add_decision(text[m.end():], msg.get("sender", "?"),
                          msg.get("channel", "general"), msg_id=msg.get("id"))


# --- models: which model and how much thinking each agent runs with ---
#
# Applied as CLI flags when council.sh starts an agent (`python council_ext.py flags <agent>`),
# so a change restarts that agent; its chat history stays in the room.

MODEL_OPTIONS = {
    "claude": {"models": ["fable", "opus", "sonnet", "haiku"],
               "efforts": ["low", "medium", "high", "xhigh", "max"]},
    "codex": {"models": ["gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-sol",
                         "gpt-6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
              "efforts": ["low", "medium", "high", "xhigh", "max"]},
    # Gemini via Antigravity CLI; its model ids are listed by `agy models` after sign-in,
    # so any model name is accepted here ("models": None)
    "agy": {"models": None, "efforts": ["low", "medium", "high", "xhigh", "max"]},
}

PRESETS = {
    "fast": {"claude": ("haiku", "low"), "codex": ("gpt-6-luna", "low"),
             "agy": ("", "low")},
    "balanced": {"claude": ("sonnet", "medium"), "codex": ("gpt-6.1-sol", "medium"),
                 "agy": ("", "medium")},
    "max": {"claude": ("opus", "high"), "codex": ("gpt-6-astra", "high"),
            "agy": ("", "high")},
}


# Who decides on commands. "ask" (default): the CLI stops and asks before every command;
# the UI shows the request with allow/deny buttons. "full" (opt-in per agent in Settings)
# runs everything without asking.
ACCESS_MODES = ("ask", "full")
ACCESS_FLAGS = {
    # ask: file edits inside the lab folder, reads and the room's tools; Bash asks
    "claude": {"ask": ["--permission-mode", "acceptEdits", "--allowedTools",
                       "mcp__agentchattr", "Read", "Grep", "Glob", "Edit", "Write"],
               "full": ["--dangerously-skip-permissions"]},
    # ask: sandboxed to the lab folder, asks to leave it (default on-request policy)
    "codex": {"ask": ["--sandbox", "workspace-write"],
              "full": ["--dangerously-bypass-approvals-and-sandbox"]},
    "agy": {"ask": ["--mode", "accept-edits"],
            "full": ["--mode", "accept-edits", "--dangerously-skip-permissions"]},
}


def is_worker(agent: str) -> bool:
    """Workers have a terminal and files; *chat agents only talk in the room."""
    return not agent.endswith("chat")


def agent_provider(agent: str, cfg: dict) -> str:
    """claude | codex | gemini, from the agent's configured command."""
    command = str(cfg.get("agents", {}).get(agent, {}).get("command", agent))
    return command if command in MODEL_OPTIONS else ""


class ModelStore:
    """data/agent_models.json: {agent: {"model": ..., "effort": ...}}; missing = CLI default."""

    def __init__(self, data_dir: str):
        self._path = Path(data_dir) / "agent_models.json"
        self._lock = threading.Lock()
        try:
            self._models = json.loads(self._path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            self._models = {}

    def get(self, agent: str) -> dict:
        with self._lock:
            return dict(self._models.get(agent, {}))

    def all(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._models.items()}

    def set(self, agent: str, provider: str, model: str = "", effort: str = "") -> dict | None:
        opts = MODEL_OPTIONS.get(provider)
        if not opts or (model and opts["models"] is not None and model not in opts["models"]) \
                or (effort and effort not in opts["efforts"]) \
                or (model and not re.fullmatch(r"[A-Za-z0-9._/-]{1,80}", model)):
            return None
        with self._lock:
            entry = {k: v for k, v in self._models.get(agent, {}).items() if k == "access"}
            entry.update({k: v for k, v in (("model", model), ("effort", effort)) if v})
            self._save(agent, entry)
        return {"model": model, "effort": effort}

    def set_access(self, agent: str, access: str) -> bool:
        """ask = the CLI asks the user before every command (default);
        full = no questions at all. Only workers have it; chat agents have no tools."""
        if access not in ACCESS_MODES or not is_worker(agent):
            return False
        with self._lock:
            entry = dict(self._models.get(agent, {}))
            entry["access"] = access
            if access == "ask":
                entry.pop("access")
            self._save(agent, entry)
        return True

    def _save(self, agent: str, entry: dict):
        if entry:
            self._models[agent] = entry
        else:
            self._models.pop(agent, None)  # back to the CLI defaults
        _atomic_write(self._path, json.dumps(self._models, indent=2) + "\n")

    def flags(self, agent: str, provider: str) -> list[str]:
        m = self.get(agent)
        model, effort = m.get("model", ""), m.get("effort", "")
        out: list[str] = []
        if is_worker(agent):
            out += ACCESS_FLAGS[provider][m.get("access", "ask")]
        if provider == "claude":
            out += ["--model", model] if model else []
            out += ["--effort", effort] if effort else []
        elif provider == "codex":
            out += ["-m", model] if model else []
            out += ["-c", f'model_reasoning_effort="{effort}"'] if effort else []
        elif provider == "agy":
            out += ["--model", model] if model else []
            out += ["--effort", effort] if effort else []
        return out


_AGENT_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,63}$")


def _pid_cwd(pid: int) -> str:
    """A process' working folder (Linux /proc, else lsof), "" when unknown."""
    proc = Path(f"/proc/{pid}/cwd")
    try:
        if proc.exists():
            return os.readlink(proc)
    except OSError:
        return ""
    if not shutil.which("lsof"):
        return ""
    try:
        r = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                           capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return next((line[1:] for line in r.stdout.splitlines() if line.startswith("n")), "")


def _pid_comm(pid: int) -> str:
    try:
        r = subprocess.run(["ps", "-o", "comm=", "-p", str(pid)], capture_output=True,
                           text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip()


def _own_pids(pattern: str, root: Path) -> list[int]:
    """Pids whose command line matches `pattern` (pgrep -f) and whose cwd is this
    install: the same scoping council.sh's own_pids uses, so another copy of the
    room on this machine is never touched."""
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True,
                           timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    roots = {str(root), str(root.resolve())}
    out = []
    for word in r.stdout.split():
        try:
            pid = int(word)
        except ValueError:
            continue
        if pid != os.getpid() and _pid_cwd(pid) in roots:
            out.append(pid)
    return out


def restart_agent(agent: str, root: Path):
    """Stop one agent of THIS install and start it again with its new flags
    (`council.sh start-one <agent>`, the same start function a full start uses).
    Blocking: the async routes call it through asyncio.to_thread.

    TMUX_TMPDIR stays ROOT/data/tmux on purpose: council.sh hard-codes that
    folder, and both must talk to the same tmux sockets."""
    if not _AGENT_NAME.fullmatch(agent):
        return
    env = {**os.environ, "COUNCIL_NO_OPEN": "1",
           "TMUX_TMPDIR": str(root / "data" / "tmux")}
    env.pop("TMUX", None)
    run = dict(env=env, capture_output=True, timeout=5, check=False)
    for cmd in (["tmux", "-L", "council-wrappers", "kill-session", "-t", f"council-{agent}"],
                ["tmux", "kill-session", "-t", f"agentchattr-{agent}"]):
        try:
            subprocess.run(cmd, **run)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for pid in _own_pids(f"wrapper.py {agent}( |$)", root):
        # the tmux server that launched the wrapper carries the same command line;
        # killing it would take every other agent down (council.sh skips it too)
        if "tmux" in _pid_comm(pid):
            continue
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    subprocess.Popen(["/bin/sh", str(root / "council.sh"), "start-one", agent],
                     cwd=str(root), env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


council: CouncilStore | None = None
models: ModelStore | None = None
_config: dict = {}
router = APIRouter()


def configure(data_dir: str, workspace: str | None = None, cfg: dict | None = None) -> CouncilStore:
    global council, models, _config
    council = CouncilStore(data_dir, workspace)
    models = ModelStore(data_dir)
    _config = cfg or {}
    return council


# --- HTTP API (all under /api/council, covered by the session-token middleware) ---

@router.get("/api/council/state")
async def get_state(channel: str = ""):
    """Everything the right-hand panels need in one call."""
    return {
        "missions": council.missions(),
        "personas": council.personas(),
        "decisions": council.decisions(channel=channel, limit=100),
    }


@router.get("/api/council/profiles")
async def get_profiles():
    return {name: agent_instructions(name, council) for name in _config.get("agents", {})}


@router.put("/api/council/profiles/{agent}")
async def put_profile(agent: str, request: Request):
    if agent not in _config.get("agents", {}):
        return JSONResponse({"error": "unknown agent"}, status_code=404)
    body = await request.json()
    instructions = body.get("instructions", "")
    if not isinstance(instructions, str) or len(instructions) > MAX_AGENT_INSTRUCTIONS:
        return JSONResponse({"error": "instructions must be text under 1800 characters"}, status_code=400)
    council.set_persona(agent, {"instructions": instructions})
    return {"agent": agent, "instructions": agent_instructions(agent, council)}


@router.put("/api/council/missions/{channel}")
async def put_mission(channel: str, request: Request):
    """{"title": "...", "body": "...", "due": "YYYY-MM-DD"}"""
    body = await request.json()
    title = str(body.get("title", "")).strip()
    if not title:
        return JSONResponse({"error": "title required"}, status_code=400)
    return council.set_mission(channel, title, str(body.get("body", "")), str(body.get("due", "")))


@router.delete("/api/council/missions/{channel}")
async def delete_mission(channel: str):
    if not council.clear_mission(channel):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True}


@router.put("/api/council/personas/{agent}")
async def put_persona(agent: str, request: Request):
    """{"title": "Architect", "avatar": "/uploads/x.png", "color": "#ffd400",
        "description": "...", "role": "Architect"} — role also drives the agent's prompt."""
    body = await request.json()
    persona = council.set_persona(agent, body)
    if "role" in body:
        import mcp_bridge
        mcp_bridge.set_role(agent, str(body.get("role") or "").strip()[:20])
    return persona


@router.delete("/api/council/personas/{agent}")
async def delete_persona(agent: str):
    if not council.clear_persona(agent):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True}


@router.get("/api/council/decisions")
async def get_decisions(channel: str = "", limit: int = 100):
    return council.decisions(channel=channel, limit=limit)


@router.post("/api/council/decisions")
async def post_decision(request: Request):
    """{"text": "...", "channel": "general", "author": "user"}"""
    body = await request.json()
    d = council.add_decision(str(body.get("text", "")), str(body.get("author", "user")),
                             str(body.get("channel", "general")))
    if d is None:
        return JSONResponse({"error": "text required"}, status_code=400)
    return d


@router.delete("/api/council/decisions/{decision_id}")
async def delete_decision(decision_id: int):
    if not council.delete_decision(decision_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True}


# --- models API ---

ROOT = Path(__file__).parent


def _models_state() -> dict:
    agents = {}
    for name in _config.get("agents", {}):
        provider = agent_provider(name, _config)
        if provider and not _config["agents"][name].get("numbered"):
            agent_cfg = _config["agents"][name]
            workspace = str(Path(agent_cfg.get("cwd", ".")).expanduser().resolve())
            chat_only = name.endswith("chat")
            agents[name] = {
                "provider": provider,
                "label": agent_cfg.get("label", name),
                "workspace": workspace,
                "mode": "chat" if chat_only else "code",
                "access": None if chat_only else "ask",
                "tools": ["MCP chat"] if chat_only else [
                    tool for tool in ("terminal", "files", "git", "terraform")
                    if tool in ("terminal", "files") or shutil.which(tool)
                ],
                **models.get(name),
            }
    return {"agents": agents, "options": MODEL_OPTIONS, "access_modes": list(ACCESS_MODES),
            "presets": {k: {p: {"model": m, "effort": e} for p, (m, e) in v.items()}
                        for k, v in PRESETS.items()}}


@router.get("/api/council/models")
async def get_models():
    """Per-agent model/effort ("" = CLI default), the choices, and the presets."""
    return _models_state()


@router.put("/api/council/models/{agent}")
async def put_model(agent: str, request: Request):
    """{"model": "opus", "effort": "high"} or {"preset": "fast|balanced|max"}; "" = default.
    Restarts the agent so the new model takes effect."""
    body = await request.json()
    provider = agent_provider(agent, _config)
    if not provider:
        return JSONResponse({"error": f"unknown agent: {agent}"}, status_code=404)
    if body.get("preset"):
        preset = PRESETS.get(body["preset"])
        if not preset:
            return JSONResponse({"error": "preset must be fast, balanced or max"}, status_code=400)
        model, effort = preset[provider]
    else:
        model, effort = str(body.get("model", "")), str(body.get("effort", ""))
    if models.set(agent, provider, model, effort) is None:
        return JSONResponse({"error": "model or effort not valid for " + provider,
                             "options": MODEL_OPTIONS[provider]}, status_code=400)
    await asyncio.to_thread(restart_agent, agent, ROOT)
    return _models_state()["agents"][agent]


@router.put("/api/council/access/{agent}")
async def put_access(agent: str, request: Request):
    """{"access": "ask"|"full"} for a worker agent; restarts it with the new permissions."""
    body = await request.json()
    if not agent_provider(agent, _config):
        return JSONResponse({"error": f"unknown agent: {agent}"}, status_code=404)
    if not models.set_access(agent, str(body.get("access", ""))):
        return JSONResponse({"error": "access must be ask or full, for a worker agent"},
                            status_code=400)
    await asyncio.to_thread(restart_agent, agent, ROOT)
    return _models_state()["agents"][agent]


@router.post("/api/council/restart/{agent}")
async def post_restart(agent: str):
    """One click: stop this agent's terminal and start it again (after a sign-in, a hang…)."""
    if agent not in _config.get("agents", {}):
        return JSONResponse({"error": f"unknown agent: {agent}"}, status_code=404)
    await asyncio.to_thread(restart_agent, agent, ROOT)
    return {"ok": True}


def _same_login(agent: str) -> list[str]:
    """Agents that share this agent's CLI sign-in (e.g. Codex and GPT Chat both use codex)."""
    cmd = str(_config.get("agents", {}).get(agent, {}).get("command", ""))
    return [n for n, a in _config.get("agents", {}).items()
            if isinstance(a, dict) and a.get("command") == cmd and not a.get("numbered")]


def _signin(agent: str) -> dict:
    """Start the CLI's own sign-in. The user finishes it in the browser window the CLI opens;
    nothing is typed or entered for them."""
    cmd = str(_config.get("agents", {}).get(agent, {}).get("command", ""))
    env = {**os.environ, "TMUX_TMPDIR": str(ROOT / "data" / "tmux")}
    env.pop("TMUX", None)
    if cmd == "codex":
        # `codex login` opens the browser and waits; when it succeeds, restart every agent on it
        def run():
            try:
                done = subprocess.run(["codex", "login"], env=env, capture_output=True, timeout=900, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return
            if done.returncode == 0:
                for name in _same_login(agent):
                    restart_agent(name, ROOT)
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "how": "browser", "restarts": _same_login(agent)}
    if cmd == "claude":
        # Claude Code signs in from inside its own terminal with /login
        for keys in (["-l", "/login"], ["Enter"]):
            subprocess.run(["tmux", "send-keys", "-t", f"agentchattr-{agent}", *keys],
                           env=env, capture_output=True, timeout=5, check=False)
        return {"ok": True, "how": "terminal"}
    # other CLIs ask for sign-in when they start: a restart brings the prompt up
    restart_agent(agent, ROOT)
    return {"ok": True, "how": "restart"}


@router.post("/api/council/signin/{agent}")
async def post_signin(agent: str):
    if agent not in _config.get("agents", {}):
        return JSONResponse({"error": f"unknown agent: {agent}"}, status_code=404)
    return await asyncio.to_thread(_signin, agent)


@router.put("/api/council/models")
async def put_all_models(request: Request):
    """{"preset": "fast|balanced|max"} for every agent at once."""
    body = await request.json()
    preset = PRESETS.get(body.get("preset", ""))
    if not preset:
        return JSONResponse({"error": "preset must be fast, balanced or max"}, status_code=400)
    for agent in _config.get("agents", {}):
        provider = agent_provider(agent, _config)
        if provider and not _config["agents"][agent].get("numbered"):
            models.set(agent, provider, *preset[provider])
            await asyncio.to_thread(restart_agent, agent, ROOT)
    return _models_state()


if __name__ == "__main__":
    # `python council_ext.py flags <agent>` — CLI flags for council.sh, one per line
    import sys
    from config_loader import load_config
    if len(sys.argv) == 3 and sys.argv[1] == "installed":
        # exit 0 if the agent's CLI is on PATH (council.sh skips the rest)
        import shutil
        cmd = load_config(ROOT).get("agents", {}).get(sys.argv[2], {}).get("command", "")
        sys.exit(0 if cmd and shutil.which(cmd) else 1)
    if len(sys.argv) == 3 and sys.argv[1] == "flags":
        cfg = load_config(ROOT)
        data_dir = Path(cfg.get("server", {}).get("data_dir", "./data"))
        store = ModelStore(str(data_dir if data_dir.is_absolute() else ROOT / data_dir))
        for flag in store.flags(sys.argv[2], agent_provider(sys.argv[2], cfg)):
            print(flag)
