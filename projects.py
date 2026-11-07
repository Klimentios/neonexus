"""Projects: the unit of work in NEONEXUS (PRODUCT.md, M1).

A project has a goal, done criteria, a lead agent, a channel where the team talks
about it, a status and a journal. Agents tick criteria off with evidence; when every
criterion is done the project goes to "review", and only a human (the browser UI)
can accept it as "done" or send it back.

Stored in data/projects.json. Mirrored to <workspace>/.council/PROJECTS.md so any
agent can read the board with plain file tools.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

STATUSES = ("active", "paused", "review", "done")
MODES = ("", "dev", "game", "ops", "red", "media", "research")
MAX_CRITERIA = 30
MAX_JOURNAL = 300
MAX_TEXT = 2000
_SLUG = re.compile(r"[^a-z0-9-]+")


def _now() -> float:
    return round(time.time(), 3)


def _clip(value, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]



def _as_list(value) -> list:
    """A single string is one item, not a list of its characters."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if isinstance(v, str)] if isinstance(value, (list, tuple)) else []

class ProjectStore:
    def __init__(self, data_dir: str, workspace: str | None = None):
        self._path = Path(data_dir) / "projects.json"
        self._workspace = Path(workspace) if workspace else None
        self._lock = threading.Lock()
        self._callbacks: list = []
        self._projects: dict[str, dict] = {}
        try:
            self._projects = json.loads(self._path.read_text("utf-8")).get("projects", {})
        except (OSError, json.JSONDecodeError, AttributeError):
            self._projects = {}

    # --- plumbing ---

    def on_change(self, callback):
        self._callbacks.append(callback)
        return self

    def _commit(self, project: dict | None, kind: str = "project"):
        """Persist, mirror to markdown, notify. Call with the lock held."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"projects": self._projects}, ensure_ascii=False, indent=1),
                       "utf-8")
        tmp.replace(self._path)
        self._mirror()
        data = dict(project) if project else {}
        for cb in list(self._callbacks):
            try:
                cb(kind, data)
            except Exception:
                pass

    def _mirror(self):
        if not self._workspace or not self._workspace.is_dir():
            return
        out = ["# Projects", "", "Written by NEONEXUS. Change them through the room's "
               "project tools, not by editing this file.", ""]
        for p in sorted(self._projects.values(), key=lambda p: -p["updated"]):
            done = sum(c["done"] for c in p["criteria"])
            out.append(f"## {p['title']} (`{p['id']}`) — {p['status']}, "
                       f"{done}/{len(p['criteria'])} done")
            out.append(f"Channel #{p['channel']}, lead {p['lead'] or '—'}"
                       + (f", mode {p['mode']}" if p["mode"] else ""))
            out.append("")
            out.append(p["goal"])
            out.append("")
            for c in p["criteria"]:
                mark = "x" if c["done"] else " "
                ev = f" — {c['evidence']}" if c.get("evidence") else ""
                out.append(f"- [{mark}] {c['text']}{ev}")
            out.append("")
        try:
            target = self._workspace / ".council" / "PROJECTS.md"
            target.parent.mkdir(exist_ok=True)
            target.write_text("\n".join(out), "utf-8")
        except OSError:
            pass

    def _journal(self, p: dict, who: str, text: str):
        p["journal"].append({"at": _now(), "by": who, "text": _clip(text, 500)})
        del p["journal"][:-MAX_JOURNAL]
        p["updated"] = _now()

    # --- reads ---

    def get(self, pid: str) -> dict | None:
        with self._lock:
            p = self._projects.get(pid)
            return json.loads(json.dumps(p)) if p else None

    def list(self) -> list[dict]:
        with self._lock:
            return sorted((json.loads(json.dumps(p)) for p in self._projects.values()),
                          key=lambda p: -p["updated"])

    def for_channel(self, channel: str) -> list[dict]:
        return [p for p in self.list() if p["channel"] == channel and p["status"] != "done"]

    # --- writes ---

    def create(self, title: str, goal: str, criteria: list[str], by: str,
               channel: str = "general", lead: str = "", mode: str = "") -> dict | str:
        title, goal = _clip(title, 120), _clip(goal)
        if not title or not goal:
            return "title and goal are required"
        if mode not in MODES:
            return f"mode must be one of {', '.join(m for m in MODES if m)}"
        criteria = [_clip(c, 300) for c in _as_list(criteria) if _clip(c, 300)][:MAX_CRITERIA]
        base = _SLUG.sub("-", title.lower()).strip("-")[:40] or "project"
        with self._lock:
            pid, n = base, 2
            while pid in self._projects:
                pid, n = f"{base}-{n}", n + 1
            p = {"id": pid, "title": title, "goal": goal, "channel": _clip(channel, 40) or "general",
                 "lead": _clip(lead, 64), "mode": mode, "status": "active",
                 "criteria": [{"id": i + 1, "text": t, "done": False, "by": "", "evidence": "",
                               "at": 0} for i, t in enumerate(criteria)],
                 "journal": [], "created": _now(), "updated": _now(), "created_by": by}
            self._journal(p, by, "created the project")
            self._projects[pid] = p
            self._commit(p)
            return json.loads(json.dumps(p))

    def update(self, pid: str, by: str, *, human: bool, **fields) -> dict | str:
        with self._lock:
            p = self._projects.get(pid)
            if not p:
                return f"no project {pid}"
            # validate everything first, so a rejected update changes nothing
            if fields.get("mode") is not None and fields["mode"] not in MODES:
                return "unknown mode"
            status = fields.get("status")
            if status is not None:
                if status not in STATUSES:
                    return f"status must be one of {', '.join(STATUSES)}"
                if status == "done" and not human:
                    return "only a human can accept a project as done; set status review"
                if p["status"] == "done" and not human:
                    return "the project is accepted; only a human can reopen it"
            changes = []
            for key in ("title", "goal", "lead", "channel"):
                if fields.get(key) is not None:
                    p[key] = _clip(fields[key], 120 if key == "title" else MAX_TEXT)
                    changes.append(key)
            if fields.get("mode") is not None:
                if fields["mode"] not in MODES:
                    return "unknown mode"
                p["mode"] = fields["mode"]
                changes.append("mode")
            status = fields.get("status")
            if status is not None:
                if status not in STATUSES:
                    return f"status must be one of {', '.join(STATUSES)}"
                # Done means a person looked at the result and accepted it.
                if status == "done" and not human:
                    return "only a human can accept a project as done; set status review"
                if p["status"] == "done" and not human:
                    return "the project is accepted; only a human can reopen it"
                p["status"] = status
                changes.append(f"status → {status}")
            for who in _as_list(fields.get("add_members")):
                who = _clip(who, 64)
                if who and who not in p.setdefault("members", []):
                    p["members"].append(who)
                    changes.append(f"member + {who}")
            for who in _as_list(fields.get("remove_members")):
                if who in p.get("members", []):
                    p["members"].remove(who)
                    changes.append(f"member − {who}")
            drop = {int(c) for c in (fields.get("remove_criteria") or []) if str(c).isdigit()} if human else set()
            if drop:
                p["criteria"] = [c for c in p["criteria"] if c["id"] not in drop]
                changes.append(f"criteria − {len(drop)}")
            for text in _as_list(fields.get("add_criteria")):
                if len(p["criteria"]) >= MAX_CRITERIA:
                    break
                if _clip(text, 300):
                    p["criteria"].append({"id": max((c["id"] for c in p["criteria"]), default=0) + 1,
                                          "text": _clip(text, 300), "done": False, "by": "",
                                          "evidence": "", "at": 0})
                    changes.append(f"criterion + {_clip(text, 60)}")
            if not changes:
                return "nothing to change"
            self._journal(p, by, "; ".join(changes))
            self._commit(p)
            return json.loads(json.dumps(p))

    def check(self, pid: str, criterion_id: int, done: bool, by: str, evidence: str = "",
              *, human: bool) -> dict | str:
        """Tick a criterion off. Agents must say what proves it (a test run, a file, a
        screenshot); a human can tick without evidence."""
        evidence = _clip(evidence, 500)
        with self._lock:
            p = self._projects.get(pid)
            if not p:
                return f"no project {pid}"
            if p["status"] == "done" and not human:
                return "the project is accepted; only a human can reopen it"
            c = next((c for c in p["criteria"] if c["id"] == criterion_id), None)
            if not c:
                return f"no criterion {criterion_id} in {pid}"
            if done and not evidence and not human:
                return "evidence is required: what shows this criterion is met?"
            c.update(done=bool(done), by=by if done else "", evidence=evidence if done else "",
                     at=_now() if done else 0)
            self._journal(p, by, f"{'✓' if done else '↺'} {c['text'][:80]}"
                          + (f" — {evidence[:120]}" if evidence else ""))
            if p["criteria"] and all(x["done"] for x in p["criteria"]) and p["status"] == "active":
                p["status"] = "review"
                self._journal(p, "system", "all criteria met; waiting for the human to accept")
            elif not done and p["status"] == "review":
                p["status"] = "active"
            self._commit(p)
            return json.loads(json.dumps(p))

    def log(self, pid: str, by: str, text: str) -> dict | str:
        if not _clip(text):
            return "text is required"
        with self._lock:
            p = self._projects.get(pid)
            if not p:
                return f"no project {pid}"
            self._journal(p, by, text)
            self._commit(p, kind="project_log")
            return json.loads(json.dumps(p))

    def delete(self, pid: str) -> bool:
        with self._lock:
            p = self._projects.pop(pid, None)
            if p:
                self._commit({"id": pid, "deleted": True})
            return bool(p)


def summary(p: dict, journal: int = 5) -> str:
    """Plain-text view for agents (MCP)."""
    done = sum(c["done"] for c in p["criteria"])
    lines = [f"Project {p['id']}: {p['title']} [{p['status']}] {done}/{len(p['criteria'])} criteria",
             f"Channel #{p['channel']}, lead {p['lead'] or '—'}"
             + (f", mode {p['mode']}" if p["mode"] else "")
             + (f", team {', '.join(p['members'])}" if p.get("members") else ""),
             f"Goal: {p['goal']}", "Done criteria:"]
    lines += [f"  {c['id']}. [{'x' if c['done'] else ' '}] {c['text']}"
              + (f" — {c['evidence']} ({c['by']})" if c["done"] and c["evidence"] else "")
              for c in p["criteria"]] or ["  (none yet — add some)"]
    if journal and p["journal"]:
        lines.append("Recent journal:")
        lines += [f"  {e['by']}: {e['text']}" for e in p["journal"][-journal:]]
    return "\n".join(lines)


# --- HTTP API (browser = the human) ---

router = APIRouter()
store: ProjectStore | None = None


def configure(data_dir: str, workspace: str | None = None) -> ProjectStore:
    global store
    store = ProjectStore(data_dir, workspace)
    return store


def _err(msg: str, code: int = 400):
    return JSONResponse({"error": msg}, status_code=code)


@router.get("/api/projects")
async def list_projects():
    return {"projects": store.list(), "statuses": list(STATUSES),
            "modes": [m for m in MODES if m]}


@router.post("/api/projects")
async def create_project(request: Request):
    """{"title", "goal", "criteria": [..], "channel"?, "lead"?, "mode"?}"""
    b = await request.json()
    r = store.create(b.get("title", ""), b.get("goal", ""), b.get("criteria") or [], "user",
                     b.get("channel", "general"), b.get("lead", ""), b.get("mode", ""))
    return _err(r) if isinstance(r, str) else r


@router.get("/api/projects/{pid}")
async def get_project(pid: str):
    p = store.get(pid)
    return p or _err("not found", 404)


@router.patch("/api/projects/{pid}")
async def patch_project(pid: str, request: Request):
    """Any of title, goal, lead, channel, mode, status ("done" = accept), add_criteria,
    remove_criteria (ids), add_members, remove_members."""
    b = await request.json()
    if not isinstance(b, dict):
        return _err("expected a JSON object")
    r = store.update(pid, "user", human=True, **{k: b.get(k) for k in
                     ("title", "goal", "lead", "channel", "mode", "status", "add_criteria",
                      "remove_criteria", "add_members", "remove_members")})
    return _err(r) if isinstance(r, str) else r


@router.post("/api/projects/{pid}/criteria/{cid}")
async def check_criterion(pid: str, cid: int, request: Request):
    """{"done": true|false, "evidence"?}"""
    b = await request.json()
    r = store.check(pid, cid, bool(b.get("done", True)), "user", b.get("evidence", ""), human=True)
    return _err(r) if isinstance(r, str) else r


@router.post("/api/projects/{pid}/journal")
async def add_journal(pid: str, request: Request):
    b = await request.json()
    r = store.log(pid, "user", b.get("text", ""))
    return _err(r) if isinstance(r, str) else r


@router.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    return {"ok": True} if store.delete(pid) else _err("not found", 404)
