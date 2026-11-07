#!/usr/bin/env python3
"""Build a clean NEONEXUS release.

Ships every file git knows about (tracked, plus untracked files that are not
ignored, e.g. new static assets, LICENSE, NOTICE.md) and drops private or
machine-specific files (see EXCLUDE_*). Without git it walks the folder.

    python3 build_release.py                 -> neonexus-{VERSION}.zip in the repo root
    python3 build_release.py --dir <path>    -> the same files copied into <path>
                                                (e.g. to start a fresh public git repo)
"""

import argparse
import fnmatch
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text().strip()
OUT_NAME = f"neonexus-{VERSION}"

# any path component with one of these names is skipped
EXCLUDE_DIRS = {".git", ".venv", "data", "uploads", "__pycache__", "node_modules"}
# exact relative paths
EXCLUDE_FILES = {
    "config.local.toml", "PRODUCT.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md",
    ".github/FUNDING.yml",
}
# file-name patterns
EXCLUDE_PATTERNS = ["*.pyc", "*.pyo", ".DS_Store", "Thumbs.db", "*.log",
                    "neonexus-*.zip", "agentchattr-*.zip"]


def _excluded(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDE_DIRS for p in parts[:-1]) or parts[-1] in EXCLUDE_DIRS:
        return True
    if rel in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in EXCLUDE_PATTERNS)


def _git_files() -> list[str] | None:
    if not (ROOT / ".git").exists() or not shutil.which("git"):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    files = {p for p in out.decode("utf-8", "surrogateescape").split("\0") if p}
    # tools/web-workspace sources are shipped even if a .gitignore rule hides them
    web = ROOT / "tools" / "web-workspace"
    if web.is_dir():
        files.update(p.relative_to(ROOT).as_posix() for p in web.rglob("*") if p.is_file())
    return sorted(files)


def _walk_files() -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file())


def release_files() -> list[str]:
    files = _git_files()
    if files is None:
        files = _walk_files()
    # skip files deleted from the working tree and anything excluded
    return [f for f in files if not _excluded(f) and (ROOT / f).is_file()]


def copy_to(dest: Path, files: list[str]) -> None:
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)  # keeps the executable bit of *.sh / *.command


def build_zip(files: list[str]) -> Path:
    out = ROOT / f"{OUT_NAME}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / OUT_NAME
        copy_to(stage, files)
        shutil.make_archive(str(ROOT / OUT_NAME), "zip", tmp, OUT_NAME)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a NEONEXUS release zip or folder.")
    ap.add_argument("--dir", help="copy the release files into this folder instead of zipping")
    args = ap.parse_args()

    files = release_files()
    if args.dir:
        dest = Path(args.dir).expanduser().resolve()
        if dest == ROOT or ROOT in dest.parents:
            print(f"--dir must be outside {ROOT}", file=sys.stderr)
            return 1
        dest.mkdir(parents=True, exist_ok=True)
        copy_to(dest, files)
        print(f"Copied {len(files)} files into {dest}")
    else:
        out = build_zip(files)
        print(f"Built {out} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
