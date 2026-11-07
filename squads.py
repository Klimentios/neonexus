"""Squads (PRODUCT.md, M2): a lead agent raises sub-agents for a task.

Each member is a real CLI (Claude Code, Codex, Antigravity) on the user's
subscription, started by the same wrapper as the main agents, under a numbered
family name (squad-codex-1, squad-claude-2…), so the main @codex is never renamed.

A member works in its own git worktree of the project folder
(<workspace>/projects/<project>/ → <workspace>/.squads/<member>/, branch squad/<member>),
so members never edit the same files. A member hands work in with squad_report (the
server commits its worktree, so a member in "ask" mode needs no shell for it); the
lead reads squad_status, then squad_merge (merge into the project's main, aborted on
conflict) or squad_message (send it back for rework).

Limits keep the subscriptions alive: 3 members per lead, 6 in all, depth 2
(a member may raise members, theirs may not), idle members stop on their own.
Access: a member never gets more than its lead has (ask < full).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
CLIS = {"claude": "squad-claude", "codex": "squad-codex", "gemini": "squad-gemini"}
PROVIDER = {"claude": "claude", "codex": "codex", "gemini": "agy"}
MAX_PER_LEAD = 3
MAX_TOTAL = 6
MAX_DEPTH = 2
IDLE_STOP_S = 45 * 60
_NAME = re.compile(r"^squad-(claude|codex|gemini)-\d{1,3}$")
_PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# what a CLI screen means (prompt for the human, quota, sign-in): screen_state.py
from screen_state import PROMPT_RE, waiting_for_human  # noqa: E402,F401

# extra flags each CLI needs to live in the room (same as council.sh)
ROOM_FLAGS = {
    "claude": [],
    "codex": ["-c", "mcp_servers.council.enabled=false",
              "-c", 'mcp_servers.agentchattr.default_tools_approval_mode="approve"'],
    "gemini": ["--settings", str(ROOT / "agy-room-permissions.json")],
}


def _tmux_env() -> dict:
    env = {**os.environ, "TMUX_TMPDIR": str(ROOT / "data" / "tmux"), "COUNCIL_NO_OPEN": "1"}
    env.pop("TMUX", None)
    return env


def _git(cwd: Path, *args, timeout: int = 20) -> subprocess.CompletedProcess:
    # core.fsmonitor=false: a member's worktree config could name an fsmonitor
    # program, and `git status` would run it as the server (same idea as hooksPath).
    return subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=timeout, check=False)


def _no_git_hang(fn):
    """A stuck git (lock, huge repo, network filesystem) answers with an error, not a raise."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except subprocess.TimeoutExpired as exc:
            words = [str(c) for c in (exc.cmd or [])[1:] if not str(c).startswith("-") and "=" not in str(c)]
            verb = words[0] if words else "command"
            return (f"error: git {verb} timed out after {exc.timeout:g} s; nothing more was done. "
                    f"Check the repository by hand, then try again.")
    return wrapper


def _git_as(who: str) -> list[str]:
    """Identity for commits the server makes; hooks off (a member could plant one)."""
    return ["-c", f"user.name={who}", "-c", "user.email=council@localhost",
            "-c", "core.hooksPath=/dev/null"]


class Squads:
    def __init__(self, data_dir: str, lab: str, registry=None, models=None, post=None,
                 wake=None):
        self._path = Path(data_dir) / "squads.json"
        self.lab = Path(lab)
        self.registry = registry
        self.models = models          # council_ext.ModelStore (for the lead's access)
        self.post = post              # post(channel, text): system message in the room
        self.wake = wake              # wake(name, channel, prompt): type a prompt into its CLI
        self._lock = threading.Lock()
        self._spawn_lock = threading.Lock()
        try:
            self.members: dict[str, dict] = json.loads(self._path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            self.members = {}

    # --- state ---

    def _save(self):
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.members, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(self._path)

    def _alive(self, name: str) -> bool:
        r = subprocess.run(["tmux", "-L", "council-wrappers", "has-session", "-t",
                            f"council-{name}"], capture_output=True, env=_tmux_env(), check=False)
        return r.returncode == 0

    def _refresh(self):
        """Drop members whose wrapper is gone (stopped, crashed, idle-stopped)."""
        with self._lock:
            for name, m in list(self.members.items()):
                if m["state"] == "running" and not self._alive(name):
                    m["state"] = "stopped"
            self._save()

    def depth(self, agent: str) -> int:
        d = 1
        while agent in self.members and d <= MAX_DEPTH + 1:
            agent = self.members[agent]["lead"]
            d += 1
        return d  # main agent = 1, its member = 2, …

    def access_of(self, agent: str) -> str:
        if agent in self.members:
            return self.members[agent]["access"]
        if self.models:
            return self.models.get(agent).get("access", "ask")
        return "ask"

    # --- workspace ---

    def project_dir(self, project: str) -> Path:
        d = self.lab / "projects" / project
        d.mkdir(parents=True, exist_ok=True)
        if not (d / ".git").exists():
            _git(d, "init", "-q", "-b", "main")
            if not any(p for p in d.iterdir() if p.name != ".git"):
                (d / "README.md").write_text(f"# {project}\n", "utf-8")
            _git(d, "add", "-A")
            _git(d, *_git_as("NEONEXUS"), "commit", "-q", "-m", "start")
        return d

    def _worktree(self, project: str, name: str) -> Path:
        repo = self.project_dir(project)
        wt = self.lab / ".squads" / name
        if wt.exists():
            return wt
        wt.parent.mkdir(exist_ok=True)
        branch = f"squad/{name}"
        has_branch = _git(repo, "rev-parse", "--verify", "-q", branch).returncode == 0
        r = _git(repo, "worktree", "add", "-q", str(wt), *([branch] if has_branch else ["-b", branch]))
        if r.returncode != 0:
            raise RuntimeError(f"git worktree: {r.stderr.strip()[:300]}")
        return wt

    # --- actions ---

    def spawn(self, lead: str, cli: str, task: str, project: str, channel: str = "general",
              model: str = "", effort: str = "", access: str = "ask") -> dict | str:
        cli = cli.lower().strip()
        if cli not in CLIS:
            return "cli must be claude, codex or gemini"
        if not _PROJECT.fullmatch(project or ""):
            return "project must be a project id (lowercase letters, digits, dashes)"
        if not task.strip():
            return "task is required: what this member must deliver"
        if model and not re.fullmatch(r"[A-Za-z0-9._/-]{1,80}", model):
            return "bad model name"
        if effort and effort not in ("low", "medium", "high", "xhigh", "max"):
            return "effort must be low, medium, high, xhigh or max"
        self._refresh()
        with self._spawn_lock:
            running = {n: m for n, m in self.members.items() if m["state"] == "running"}
            if len(running) >= MAX_TOTAL:
                return f"squad limit: {MAX_TOTAL} members run already; stop one first"
            if sum(m["lead"] == lead for m in running.values()) >= MAX_PER_LEAD:
                return f"you lead {MAX_PER_LEAD} members already; stop or reuse one"
            if self.depth(lead) >= MAX_DEPTH + 1:
                return "members of members can't raise more members (depth limit 2)"
            # never more access than the lead has
            access = "full" if access == "full" and self.access_of(lead) == "full" else "ask"

            base = CLIS[cli]
            taken = set(self.members) | set(self.registry.get_all() if self.registry else {})
            slot = 1
            while f"{base}-{slot}" in taken:
                slot += 1
            name = f"{base}-{slot}"
            try:
                wt = self._worktree(project, name)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                return f"could not make the worktree: {exc}"

            import council_ext
            flags = list(council_ext.ACCESS_FLAGS[PROVIDER[cli]][access]) + ROOM_FLAGS[cli]
            if cli == "codex":
                # a fresh worktree is a new git root: trust it for this session only
                flags += ["-c", f'projects."{wt}".trust_level="trusted"']
            if model:
                flags += ["-m" if cli == "codex" else "--model", model]
            if effort:
                flags += (["-c", f'model_reasoning_effort="{effort}"'] if cli == "codex"
                          else ["--effort", effort])
            cmd = (f"unset TMUX; .venv/bin/python wrapper.py {base} --slot {slot} "
                   f"--cwd {shlex.quote(str(wt))} --no-restart "
                   f"--label {shlex.quote(name)} " + " ".join(shlex.quote(f) for f in flags))
            env = _tmux_env()
            r = subprocess.run(["tmux", "-L", "council-wrappers", "new-session", "-d", "-s",
                                f"council-{name}", cmd], cwd=str(ROOT), env=env,
                               capture_output=True, text=True, check=False)
            if r.returncode != 0:
                return f"could not start: {r.stderr.strip()[:300]}"
            (ROOT / "data" / "logs").mkdir(parents=True, exist_ok=True)
            subprocess.run(["tmux", "-L", "council-wrappers", "pipe-pane", "-o", "-t",
                            f"council-{name}", f"cat >> {shlex.quote(str(ROOT / 'data' / 'logs' / (name + '.log')))}"],
                           env=env, capture_output=True, check=False)
            member = {"name": name, "cli": cli, "lead": lead, "project": project,
                      "channel": channel, "task": task.strip()[:4000], "worktree": str(wt),
                      "branch": f"squad/{name}", "access": access, "model": model,
                      "effort": effort, "state": "running", "started": time.time(),
                      "last_seen": time.time()}
            with self._lock:
                self.members[name] = member
                self._save()
            # agy reads one shared MCP file at start: hold the next spawn until it loaded
            if cli == "gemini":
                time.sleep(12)
        threading.Thread(target=self._brief, args=(member,), daemon=True).start()
        return dict(member)

    def _brief(self, m: dict):
        """Once the member is registered, give it its task in the room."""
        for _ in range(90):
            if self.registry and m["name"] in self.registry.get_all():
                break
            time.sleep(2)
        else:
            if self.post:
                self.post(m["channel"], f"@{m['lead']} {m['name']} did not come online in 3 min "
                          f"(first-run screen? see its terminal). squad_stop it or retry.")
            return
        if not self._wait_settled(m):
            if self.post:
                self.post(m["channel"], f"@{m['lead']} {m['name']} never got ready (an "
                          f"unanswered question in its terminal?). squad_stop it or retry.")
            return
        # The task goes straight into the member's prompt: told only "you're mentioned",
        # a fresh member reads the whole room and picks up someone else's request.
        prompt = (f"You are {m['name']}, a squad member of {m['lead']} on project "
                  f"{m['project']}. Your current folder is a git worktree on branch "
                  f"{m['branch']}: work and commit only here. YOUR TASK: {m['task']} "
                  f"Ignore requests in the room addressed to other agents. Do not merge into "
                  f"main. When done, call the squad_report MCP tool (sender={m['name']}) with a "
                  f"summary of what you built and the evidence (commands you ran and their "
                  f"output): it commits your worktree for you and notifies @{m['lead']}.")
        if self.post:  # a copy for the human, not routed to the member (no @mention)
            self.post(m["channel"], f"Squad: {m['name']} ({m['cli']}) started for "
                      f"@{m['lead']} on `{m['project']}`, branch {m['branch']}. Task: {m['task']}")
        if self.wake:
            self.wake(m["name"], m["channel"], " ".join(prompt.split()))

    def _screen(self, name: str) -> str:
        r = subprocess.run(["tmux", "capture-pane", "-p", "-t", f"agentchattr-{name}"],
                           capture_output=True, text=True, env=_tmux_env(), check=False)
        return r.stdout if r.returncode == 0 else ""

    def _wait_settled(self, m: dict, limit_s: int = 120, human_s: int = 30 * 60):
        """A CLI that just started still prints warnings and MCP status for a few seconds;
        a mention injected then is lost. Wait for its input prompt and a screen that has
        not changed for 6 s (max limit_s). A folder-trust or permission question is the
        human's: typing the task into it once picked "No, exit". Ask for an answer and
        wait for it (up to human_s); returns False if it never came."""
        from wrapper_unix import get_ready_checker
        ready = get_ready_checker(f"agentchattr-{m['name']}", provider=PROVIDER[m["cli"]])
        deadline = time.time() + limit_s
        last, stable_since, asked = None, time.time(), False
        while time.time() < deadline:
            screen = self._screen(m["name"])
            if waiting_for_human(screen):
                if not asked:
                    asked, deadline = True, time.time() + human_s
                    if self.post:
                        self.post(m["channel"], f"Squad: {m['name']} waits for the user's "
                                  f"answer in its terminal (folder trust or a permission). "
                                  f"Its task starts after that.")
                last = None  # after the answer, wait for a fresh stable screen
                time.sleep(2)
                continue
            if screen != last:
                last, stable_since = screen, time.time()
            elif ready() and time.time() - stable_since >= 6:
                return True
            time.sleep(1)
        return False

    # --- hand-in, review, merge ---

    def _ahead(self, m: dict) -> int:
        out = _git(Path(m["worktree"]), "rev-list", "--count", "main..HEAD").stdout.strip()
        return int(out) if out.isdigit() else 0

    @_no_git_hang
    def report(self, name: str, summary: str, evidence: str = "") -> str:
        """A member hands its work in: commit what is in its worktree, tell the lead."""
        m = self.members.get(name)
        if not m:
            return "only squad members report; you are not one"
        summary, evidence = summary.strip()[:1500], evidence.strip()[:1500]
        if not summary:
            return "summary is required: what you built"
        wt = Path(m["worktree"])
        if not wt.is_dir():
            return f"your worktree {wt} is gone"
        if _git(wt, "status", "--porcelain").stdout.strip():
            _git(wt, "add", "-A")
            body = summary + (f"\n\nEvidence: {evidence}" if evidence else "")
            r = _git(wt, *_git_as(name), "commit", "-q", "-m",
                     f"{name}: {summary.splitlines()[0][:60]}", "-m", body)
            if r.returncode != 0:
                return f"commit failed: {(r.stderr or r.stdout).strip()[:300]}"
        ahead = self._ahead(m)
        if not ahead:
            return "nothing to hand in: your branch has no commits ahead of main"
        head = _git(wt, "rev-parse", "--short", "HEAD").stdout.strip()
        stat = _git(wt, "diff", "--shortstat", "main...HEAD").stdout.strip()
        with self._lock:
            m.update(review="reported", report={"summary": summary, "evidence": evidence,
                                                "head": head, "at": time.time()},
                     last_seen=time.time())
            self._save()
        if self.post:  # @lead: the router wakes the lead with this
            self.post(m["channel"], f"@{m['lead']} {name} handed in `{m['project']}`: "
                      f"{m['branch']} @ {head}, {ahead} commit(s), {stat}.\n{summary}"
                      + (f"\nEvidence: {evidence}" if evidence else "")
                      + f"\nReview it (squad_status), then squad_merge or squad_message "
                      f"to send it back.")
        return (f"Handed in: {m['branch']} @ {head} ({ahead} commit(s) ahead of main). "
                f"@{m['lead']} was notified; wait for its review.")

    @_no_git_hang
    def merge(self, requester: str, name: str, human: bool = False) -> str:
        """The lead accepts a member's branch into the project's main."""
        m = self.members.get(name)
        if not m:
            return f"no member {name}"
        if not human and requester != m["lead"]:
            return f"only the lead ({m['lead']}) or the user can merge {name}"
        repo = self.lab / "projects" / m["project"]
        wt = Path(m["worktree"])
        if wt.is_dir() and _git(wt, "status", "--porcelain").stdout.strip():
            return f"{name} has uncommitted work; it must squad_report first"
        if _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
            return f"{repo} is not on main; fix it by hand first"
        if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
            return f"{repo} (main) has uncommitted changes; commit or drop them first"
        if _git(repo, "rev-list", "--count", f"main..{m['branch']}").stdout.strip() in ("", "0"):
            return f"nothing to merge: {m['branch']} has no commits that main lacks"
        r = _git(repo, *_git_as(requester), "merge", "--no-ff", "-m",
                 f"Merge {m['branch']} ({name} for {m['lead']})", m["branch"], timeout=60)
        if r.returncode != 0:
            conflicts = _git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()
            _git(repo, "merge", "--abort")
            with self._lock:
                m["review"] = "conflict"
                self._save()
            files = ", ".join(conflicts[:20]) or (r.stderr or r.stdout).strip()[:300]
            return (f"Conflict, merge aborted; main is unchanged. Files: {files}. Send it back "
                    f"with squad_message: {name} should merge main into its branch, resolve, "
                    f"and squad_report again.")
        head = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        with self._lock:
            m["review"] = "merged"
            self._save()
        if self.post:
            self.post(m["channel"], f"Squad: {m['branch']} merged into `{m['project']}` "
                      f"main @ {head} by {requester}.")
        return f"Merged {m['branch']} into main @ {head} in {repo}."

    def message(self, requester: str, name: str, text: str, human: bool = False) -> str:
        """The lead sends a member back for rework (typed straight into its CLI)."""
        m = self.members.get(name)
        if not m:
            return f"no member {name}"
        if not human and requester != m["lead"]:
            return f"only the lead ({m['lead']}) or the user can direct {name}"
        text = " ".join(text.split())[:3000]
        if not text:
            return "text is required"
        if m["state"] != "running":
            return f"{name} is {m['state']}; spawn a new member instead"
        with self._lock:
            m["review"] = "rework"
            self._save()
        if self.post:
            self.post(m["channel"], f"Squad: {requester} → {name}: {text}")
        if self.wake:
            self.wake(name, m["channel"], f"From your lead {requester}: {text} When done, "
                      f"call squad_report (sender={name}) again.")
        return f"Sent to {name}."

    def stop(self, requester: str, name: str, human: bool = False, remove: bool = False) -> str:
        if not _NAME.fullmatch(name or ""):
            return "not a squad member name"
        m = self.members.get(name)
        if not m:
            return f"no member {name}"
        if not human and requester not in (m["lead"], name):
            return f"only the lead ({m['lead']}) or the user can stop {name}"
        env = _tmux_env()
        subprocess.run(["tmux", "-L", "council-wrappers", "kill-session", "-t", f"council-{name}"],
                       env=env, capture_output=True, check=False)
        subprocess.run(["tmux", "kill-session", "-t", f"agentchattr-{name}"],
                       env=env, capture_output=True, check=False)
        note = ""
        if remove:
            repo = self.lab / "projects" / m["project"]
            dirty = _git(Path(m["worktree"]), "status", "--porcelain").stdout.strip()
            if dirty:
                note = " Worktree kept: it has uncommitted changes."
            else:
                _git(repo, "worktree", "remove", m["worktree"])
                note = f" Worktree removed; branch {m['branch']} kept."
        with self._lock:
            m["state"] = "stopped"
            self._save()
        return f"{name} stopped.{note}"

    def status(self, lead: str = "", project: str = "") -> list[dict]:
        self._refresh()
        with self._lock:  # snapshot: spawn/stop may change the dict while git runs
            members = [dict(m) for m in self.members.values()]
        out = []
        for info in members:
            if (lead and info["lead"] != lead) or (project and info["project"] != project):
                continue
            wt = Path(info["worktree"])
            if wt.is_dir():
                try:
                    info["ahead"] = _git(wt, "rev-list", "--count", "main..HEAD").stdout.strip()
                    info["diff"] = _git(wt, "diff", "--stat", "main...HEAD").stdout.strip()[-1500:]
                    info["uncommitted"] = _git(wt, "status", "--porcelain").stdout.strip()[:800]
                except subprocess.TimeoutExpired:
                    info["error"] = "git timed out reading this worktree"
            out.append(info)
        return sorted(out, key=lambda m: m["started"])

    def reap_idle(self, now: float | None = None):
        """Stop running members nobody heard from for IDLE_STOP_S (called by the server)."""
        now = now or time.time()
        online = self.registry.get_all() if self.registry else {}
        for name, m in list(self.members.items()):
            if m["state"] != "running":
                continue
            if name in online:
                m["last_seen"] = now
            elif now - m.get("last_seen", now) > IDLE_STOP_S:
                self.stop("system", name, human=True)


def describe(m: dict) -> str:
    lines = [f"{m['name']} [{m['state']}] {m['cli']} lead={m['lead']} project={m['project']} "
             f"access={m['access']} branch={m['branch']}",
             f"  task: {m['task'][:300]}",
             f"  worktree: {m['worktree']}"]
    if m.get("review"):
        lines.append(f"  review: {m['review']}")
    if m.get("report"):
        lines.append(f"  report: {m['report']['summary'][:400]}"
                     + (f" | evidence: {m['report']['evidence'][:300]}" if m['report'].get('evidence') else ""))
    if m.get("ahead"):
        lines.append(f"  commits ahead of main: {m['ahead']}")
    if m.get("diff"):
        lines.append("  diff vs main:\n    " + m["diff"].replace("\n", "\n    "))
    if m.get("uncommitted"):
        lines.append("  uncommitted:\n    " + m["uncommitted"].replace("\n", "\n    "))
    return "\n".join(lines)


squads: Squads | None = None


def configure(data_dir: str, lab: str, registry=None, models=None, post=None,
              wake=None, reaper: bool = True) -> Squads:
    global squads
    squads = Squads(data_dir, lab, registry, models, post, wake)
    if reaper:
        def loop(s=squads):
            while squads is s:
                time.sleep(60)
                try:
                    s.reap_idle()
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True, name="squad-reaper").start()
    return squads


# --- HTTP API (the browser = the human) ---

from fastapi import APIRouter  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

router = APIRouter()


@router.get("/api/squads")
async def list_squads(lead: str = "", project: str = ""):
    import asyncio
    members = await asyncio.to_thread(squads.status, lead, project)
    return {"members": members, "limits": {"per_lead": MAX_PER_LEAD, "total": MAX_TOTAL,
                                           "depth": MAX_DEPTH, "idle_stop_min": IDLE_STOP_S // 60}}


@router.post("/api/squads/{name}/merge")
async def merge_member(name: str):
    import asyncio
    msg = await asyncio.to_thread(squads.merge, "user", name, True)
    return JSONResponse({"result": msg}, status_code=200 if msg.startswith("Merged") else 400)


@router.delete("/api/squads/{name}")
async def stop_member(name: str, remove: bool = False):
    import asyncio
    msg = await asyncio.to_thread(squads.stop, "user", name, True, remove)
    return JSONResponse({"result": msg}, status_code=200 if "stopped" in msg else 400)
