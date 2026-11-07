"""Code mode: one button from a task to reviewed code.

The user writes a task and picks who builds and who reviews. NEONEXUS then
  * makes a folder for it inside the workspace (or uses an existing one) and records a git
    starting point there, so every change the agents make can be shown afterwards;
  * opens a project with done criteria and a channel of its own;
  * hands the task to the builder and, once the builder has reported, to the reviewer
    (the room's turn order wakes them one after another);
  * shows the changes since the start; "Accept" commits them and closes the project,
    "Send back" returns the task to the builder with the user's note.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

MAX_DIFF = 200_000
_SLUG = re.compile(r"[^a-z0-9]+")
_GIT = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "user.name=NEONEXUS", "-c", "user.email=neonexus@localhost"]


def _git(folder: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run([*_GIT, "-C", str(folder), *args], capture_output=True, text=True,
                          timeout=timeout, check=False)


def slugify(text: str, limit: int = 14) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")[:limit].strip("-") or "task"


class CodeMode:
    def __init__(self, data_dir: str, workspace: str, projects, post, ensure_channel):
        self.path = Path(data_dir) / "codemode.json"
        self.workspace = Path(workspace).expanduser().resolve()
        self.projects = projects          # projects.ProjectStore
        self.post = post                  # post(channel, sender, text) → message routed like any other
        self.ensure_channel = ensure_channel
        self._lock = threading.Lock()
        try:
            self.tasks: dict[str, dict] = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            self.tasks = {}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(self.path)

    # --- folders ---
    def folders(self) -> list[str]:
        """Existing top-level folders in the workspace, to pick one instead of a new folder."""
        if not self.workspace.is_dir():
            return []
        return sorted(p.name for p in self.workspace.iterdir()
                      if p.is_dir() and not p.name.startswith(".") and p.name not in ("node_modules",))

    def _folder(self, name: str) -> Path | None:
        name = (name or "").strip().rstrip("/")
        if (not name or name.startswith((".", "/", "~", "\\")) or ".." in Path(name).parts
                or Path(name).is_absolute() or re.match(r"^[A-Za-z]:", name)):
            return None
        folder = (self.workspace / name).resolve()
        return folder if folder.is_relative_to(self.workspace) and folder != self.workspace else None

    def _baseline(self, folder: Path) -> str:
        """A commit to compare against. A folder that is not a git repository yet becomes one."""
        if _git(folder, "rev-parse", "--is-inside-work-tree").returncode != 0 or \
                Path(_git(folder, "rev-parse", "--show-toplevel").stdout.strip() or "/").resolve() != folder:
            _git(folder, "init", "-q")
        _git(folder, "add", "-A")
        _git(folder, "commit", "-q", "--allow-empty", "-m", "NEONEXUS Code mode: starting point")
        return _git(folder, "rev-parse", "HEAD").stdout.strip()

    # --- start ---
    async def start(self, task: str, folder: str, builder: str, reviewer: str, by: str = "user") -> dict | str:
        task = (task or "").strip()
        if len(task) < 3:
            return "describe the task"
        if not builder:
            return "pick who writes the code"
        if reviewer == builder:
            reviewer = ""
        slug = slugify(folder or task)
        target = self._folder(folder or slug)
        if not target:
            return "the folder must be inside the workspace"
        target.mkdir(parents=True, exist_ok=True)
        try:
            base = self._baseline(target)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"git is needed for Code mode: {e}"
        if not base:
            return "could not create a git starting point in that folder (is git installed?)"
        rel = target.relative_to(self.workspace).as_posix()
        channel = "code-" + slugify(rel)
        with self._lock:
            n, cid = 2, channel
            while cid in self.tasks:
                cid, n = f"{channel[:17]}-{n}", n + 1
            channel = cid
        await self.ensure_channel(channel)
        criteria = [f"the task is done in {rel}/",
                    "tests or a run show it works (output in the report)"]
        if reviewer:
            criteria.append(f"{reviewer} reviewed the changes and approved")
        p = self.projects.create(task[:120], task, criteria, by, channel=channel, lead=builder, mode="dev")
        if isinstance(p, str):
            return p
        if reviewer:
            self.projects.update(p["id"], by, human=True, add_members=[reviewer])
        entry = {"id": channel, "task": task, "folder": rel, "base": base, "builder": builder,
                 "reviewer": reviewer, "project": p["id"], "channel": channel, "status": "working",
                 "created": time.time()}
        with self._lock:
            self.tasks[channel] = entry
            self._save()
        self.post(channel, by, self._brief(entry))
        return entry

    def _brief(self, t: dict) -> str:
        review = (f"\n\nThen @{t['reviewer']}: review the changes (`git diff {t['base'][:10]}` in that folder), "
                  "answer **approve** or list concrete fixes, and tick the review criterion when you approve."
                  if t["reviewer"] else "")
        return (f"@{t['builder']} Code mode task: {t['task']}\n\n"
                f"Work only in the workspace folder `{t['folder']}/`. Build it, run it or its tests, then report "
                f"what changed and the real output, and tick the project's criteria with that evidence."
                + review)

    # --- review ---
    def changes(self, cid: str) -> dict | str:
        t = self.tasks.get(cid)
        if not t:
            return "no such Code mode task"
        folder = self._folder(t["folder"])
        if not folder or not folder.is_dir():
            return "the task folder is gone"
        _git(folder, "add", "-A", "--intent-to-add")
        stat = _git(folder, "diff", "--stat", t["base"]).stdout
        diff = _git(folder, "diff", t["base"]).stdout
        files = [ln.split("\t")[-1] for ln in _git(folder, "diff", "--name-status", t["base"]).stdout.splitlines() if ln]
        return {**t, "files": files, "stat": stat.strip(),
                "diff": diff[:MAX_DIFF], "truncated": len(diff) > MAX_DIFF}

    def accept(self, cid: str, by: str = "user") -> dict | str:
        t = self.tasks.get(cid)
        if not t:
            return "no such Code mode task"
        folder = self._folder(t["folder"])
        if not folder:
            return "the task folder is gone"
        _git(folder, "add", "-A")
        _git(folder, "commit", "-q", "--allow-empty", "-m", f"Code mode: {t['task'][:72]}")
        self.projects.update(t["project"], by, human=True, status="done")
        with self._lock:
            t["status"] = "accepted"
            self._save()
        self.post(t["channel"], "system", f"Accepted and committed in `{t['folder']}/`. Thanks, everyone.")
        return t

    def send_back(self, cid: str, note: str, by: str = "user") -> dict | str:
        t = self.tasks.get(cid)
        if not t:
            return "no such Code mode task"
        note = (note or "").strip()[:2000] or "please look again"
        with self._lock:
            t["status"] = "working"
            self._save()
        follow = f" Then @{t['reviewer']} reviews again." if t["reviewer"] else ""
        self.post(t["channel"], by, f"@{t['builder']} not done yet: {note}{follow}")
        return t

    def list(self) -> list[dict]:
        return sorted(self.tasks.values(), key=lambda t: -t.get("created", 0))


codemode: CodeMode | None = None


def configure(data_dir: str, workspace: str, projects, post, ensure_channel) -> CodeMode:
    global codemode
    codemode = CodeMode(data_dir, workspace, projects, post, ensure_channel)
    return codemode


router = APIRouter()


def _err(msg: str, code: int = 400):
    return JSONResponse({"error": msg}, status_code=code)


@router.get("/api/codemode")
async def list_tasks():
    return {"tasks": codemode.list(), "folders": codemode.folders(), "workspace": str(codemode.workspace)}


@router.post("/api/codemode")
async def start_task(request: Request):
    """{"task", "folder"?, "builder", "reviewer"?}"""
    b = await request.json()
    if not isinstance(b, dict):
        return _err("expected a JSON object")
    r = await codemode.start(str(b.get("task", "")), str(b.get("folder", "")),
                             str(b.get("builder", "")), str(b.get("reviewer", "")))
    return _err(r) if isinstance(r, str) else r


@router.get("/api/codemode/{cid}/changes")
async def get_changes(cid: str):
    import asyncio
    r = await asyncio.to_thread(codemode.changes, cid)
    return _err(r, 404) if isinstance(r, str) else r


@router.post("/api/codemode/{cid}/accept")
async def accept(cid: str):
    import asyncio
    r = await asyncio.to_thread(codemode.accept, cid)
    return _err(r, 404) if isinstance(r, str) else r


@router.post("/api/codemode/{cid}/send-back")
async def send_back(cid: str, request: Request):
    b = await request.json()
    r = codemode.send_back(cid, str((b or {}).get("note", "")) if isinstance(b, dict) else "")
    return _err(r, 404) if isinstance(r, str) else r
