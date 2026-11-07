"""Local code workspace beside the chat: bounded file editing and a PTY shell."""

import asyncio
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

router = APIRouter()
_root: Path | None = None
_session_token = ""
MAX_FILE_BYTES = 512 * 1024
HIDDEN_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".DS_Store", "data"}
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".html",
                 ".css", ".scss", ".sh", ".tf", ".tfvars", ".go", ".rs", ".java",
                 ".kt", ".swift", ".yaml", ".yml", ".sql", ".xml", ".c", ".h",
                 ".cpp", ".hpp", ".asm", ".s", ".toml", ".txt", ".bat", ".ps1"}
TEXT_NAMES = {"LICENSE", "Dockerfile", "Makefile", "AGENTS.md"}


def configure(root: str, session_token: str):
    global _root, _session_token
    _root = Path(root).expanduser().resolve()
    _session_token = session_token


def _safe_path(relative: str) -> Path | None:
    if not _root or not relative or relative.startswith("/"):
        return None
    parts = Path(relative).parts
    if any(part in ("..", ".") or part.startswith(".") or part in HIDDEN_NAMES for part in parts):
        return None
    path = (_root / relative).resolve()
    if not path.is_relative_to(_root):
        return None
    return path


@router.get("/api/workspace/tree")
async def tree():
    if not _root or not _root.is_dir():
        return JSONResponse({"error": "workspace unavailable"}, status_code=503)
    files = []
    for base, dirs, names in os.walk(_root):
        depth = len(Path(base).relative_to(_root).parts)
        dirs[:] = sorted(d for d in dirs if d not in HIDDEN_NAMES and not d.startswith(".")) if depth < 5 else []
        for name in sorted(names):
            if name.startswith(".") or name in HIDDEN_NAMES:
                continue
            path = Path(base) / name
            if (path.is_file() and not path.is_symlink() and
                    (path.suffix.lower() in TEXT_SUFFIXES or name in TEXT_NAMES) and
                    path.stat().st_size <= MAX_FILE_BYTES):
                files.append(path.relative_to(_root).as_posix())
                if len(files) >= 500:
                    return {"root": str(_root), "files": files, "truncated": True}
    return {"root": str(_root), "files": files, "truncated": False}


@router.get("/api/workspace/file")
async def read_file(path: str):
    target = _safe_path(path)
    if not target or not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
        return JSONResponse({"error": "file unavailable"}, status_code=404)
    try:
        content = target.read_text("utf-8")
    except (UnicodeError, OSError):
        return JSONResponse({"error": "not a UTF-8 text file"}, status_code=415)
    return {"path": path, "content": content, "revision": str(target.stat().st_mtime_ns)}


@router.put("/api/workspace/file")
async def write_file(request: Request):
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content")
    revision = body.get("revision")
    target = _safe_path(path) if isinstance(path, str) else None
    if not target or not target.is_file() or not isinstance(content, str):
        return JSONResponse({"error": "file unavailable"}, status_code=404)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        return JSONResponse({"error": "file too large"}, status_code=413)
    if str(target.stat().st_mtime_ns) != revision:
        return JSONResponse({"error": "file changed on disk; reload before saving"}, status_code=409)
    fd, temp_path = tempfile.mkstemp(prefix=".agentchattr-", dir=target.parent)
    try:
        os.fchmod(fd, target.stat().st_mode & 0o777)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        os.replace(temp_path, target)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return {"path": path, "revision": str(target.stat().st_mtime_ns)}


@router.websocket("/ws/workspace")
async def terminal(websocket: WebSocket):
    import app  # Host/Origin check shared with the rest of the server
    if (not app.ws_allowed(websocket) or websocket.query_params.get("token") != _session_token
            or not _root or not _root.is_dir()):
        await websocket.close(code=1008)
        return
    if sys.platform == "win32":  # no PTY on Windows: the editor still works, the shell does not
        await websocket.accept()
        await websocket.send_text("The built-in terminal needs macOS or Linux.\r\n")
        await websocket.close(code=1000)
        return
    import fcntl, pty, termios  # noqa: E401  (POSIX only)
    await websocket.accept()
    master, slave = pty.openpty()
    shell = os.environ.get("SHELL") or shutil.which("zsh") or shutil.which("bash") or "/bin/sh"
    process = subprocess.Popen(
        [shell, "-l"], cwd=_root, stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True, close_fds=True,
    )
    os.close(slave)

    async def output():
        while process.poll() is None:
            try:
                data = await asyncio.to_thread(os.read, master, 4096)
            except OSError:
                break
            if not data:
                break
            await websocket.send_text(data.decode("utf-8", errors="replace"))

    output_task = asyncio.create_task(output())
    try:
        while True:
            payload = json.loads(await websocket.receive_text())
            if payload.get("type") == "input":
                data = str(payload.get("data", ""))[:4096].encode("utf-8")
                await asyncio.to_thread(os.write, master, data)
            elif payload.get("type") == "resize":
                cols = min(max(int(payload.get("cols", 80)), 20), 300)
                rows = min(max(int(payload.get("rows", 24)), 5), 100)
                fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except (WebSocketDisconnect, OSError, ValueError, json.JSONDecodeError):
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.to_thread(process.wait, timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait)
        output_task.cancel()
        await asyncio.gather(output_task, return_exceptions=True)
        os.close(master)
