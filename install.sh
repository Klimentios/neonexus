#!/usr/bin/env sh
# NEONEXUS - one-command install for macOS and Linux.
# Installs what is missing (Python 3.11+, tmux, the Python packages in .venv),
# starts the room and opens it in the browser. Safe to run again: it only adds
# what is missing. The agents' folders (~/NEONEXUS) are created by the app.
#
#   sh install.sh                     install and start
#   NEONEXUS_NO_START=1 sh install.sh install only
cd "$(dirname "$0")" || exit 1
ROOT=$(pwd)
OS=$(uname -s)

say()  { printf '\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m  + %s\033[0m\n' "$1"; }
die()  { printf '\n\033[31mInstall failed: %s\033[0m\n' "$1" >&2; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }

# run as root: directly when we are root (containers), else through sudo
as_root() {
    if [ "$(id -u)" = 0 ]; then "$@"
    elif has sudo; then sudo "$@"
    else warn "Need root rights to run: $*"; return 1
    fi
}

APT_UPDATED=""
# pkg_install <brew name> <linux name>: Homebrew on macOS, the system package manager on Linux
pkg_install() {
    if [ "$OS" = "Darwin" ]; then
        has brew || return 1
        brew install "$1"
    elif has apt-get; then
        if [ -z "$APT_UPDATED" ]; then as_root apt-get update -qq || return 1; APT_UPDATED=1; fi
        as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$2"
    elif has dnf; then as_root dnf install -y "$2"
    elif has pacman; then as_root pacman -S --noconfirm --needed "$2"
    elif has zypper; then as_root zypper --non-interactive install "$2"
    else return 1
    fi
}

# NEONEXUS_NO_BREW=1 ignores Homebrew (tests the path of a Mac without it)
if [ -n "$NEONEXUS_NO_BREW" ]; then
    has() { [ "$1" != brew ] && command -v "$1" >/dev/null 2>&1; }
fi
# Homebrew may be installed but not on PATH yet (fresh shell after its installer)
if [ "$OS" = "Darwin" ] && [ -z "$NEONEXUS_NO_BREW" ] && ! has brew; then
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [ -x "$b" ]; then eval "$("$b" shellenv)"; break; fi
    done
fi

say "NEONEXUS installer ($OS)"

# ---------------------------------------------------------------- 1. Python 3.11+
py_ok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; }

find_py() {
    for p in python3.14 python3.13 python3.12 python3.11 python3; do
        has "$p" || continue
        cand=$(command -v "$p")
        # on a Mac without the Command Line Tools /usr/bin/python3 is only a stub that
        # pops up an "install developer tools" dialog; skip it
        if [ "$OS" = "Darwin" ] && [ "$cand" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
            continue
        fi
        if py_ok "$cand"; then PY="$cand"; return 0; fi
    done
    return 1
}

UV=""
find_uv() {
    if has uv; then UV=$(command -v uv); return 0; fi
    for u in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$u" ]; then UV="$u"; return 0; fi
    done
    return 1
}

# uv (https://docs.astral.sh/uv) brings its own Python without Homebrew or root
ensure_uv() {
    find_uv && return 0
    say "Installing uv (Python manager) into ~/.local/bin"
    if ! has curl && ! has wget; then
        pkg_install curl curl || { warn "Need curl or wget to download uv."; return 1; }
        has apt-get && { pkg_install ca-certificates ca-certificates || true; }
    fi
    if has curl; then
        curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh
    else
        wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh
    fi
    find_uv
}

PY=""
PY_FROM_UV=""
if ! find_py; then
    say "Installing Python 3.12"
    if [ "$OS" = "Darwin" ]; then
        if has brew; then
            brew install python@3.12 || warn "brew install python@3.12 failed"
            BREW_PY="$(brew --prefix)/bin/python3.12"
            if [ -x "$BREW_PY" ] && py_ok "$BREW_PY"; then PY="$BREW_PY"; else find_py || true; fi
        fi
    else
        # the distro's python3 may be older than 3.11 (Ubuntu 22.04 has 3.10); checked below
        pkg_install python3 python3 || warn "Could not install python3 with the package manager"
        find_py || true
    fi
fi
if [ -z "$PY" ]; then
    # no Homebrew, or the package manager's Python is too old: use uv
    ensure_uv || die "No Python 3.11+ found and uv could not be installed. Install Python 3.12 (python.org) and run this again."
    "$UV" python install 3.12 || die "uv could not install Python 3.12"
    PY=$("$UV" python find 3.12) || die "uv installed Python 3.12 but cannot find it"
    PY_FROM_UV=1
fi
py_ok "$PY" || die "$PY is older than Python 3.11"
ok "Python: $("$PY" --version 2>&1) ($PY)"

# ---------------------------------------------------------------- 2. tmux
# every agent CLI runs in its own terminal session; the room itself works without it
if ! has tmux; then
    say "Installing tmux"
    if [ "$OS" = "Darwin" ] && ! has brew; then
        warn "tmux is not installed. The room, chat, projects and Connect AI work without it;"
        warn "the agent terminals and squads need it. Install Homebrew from https://brew.sh,"
        warn "then run: brew install tmux  (and this installer again)."
    else
        pkg_install tmux tmux || warn "Could not install tmux. The room works; agent terminals and squads need tmux."
    fi
fi
has tmux && ok "tmux: $(tmux -V)"

# ---------------------------------------------------------------- 3. Python packages in .venv
say "Preparing the Python environment"
venv_ok() { [ -x .venv/bin/python ] && py_ok .venv/bin/python && .venv/bin/python -m pip --version >/dev/null 2>&1; }

if [ -e .venv ] && ! venv_ok; then
    warn "Existing .venv is broken or too old, recreating it"
    rm -rf .venv
fi
if [ ! -e .venv ]; then
    if [ -n "$PY_FROM_UV" ]; then
        "$UV" venv --seed --python "$PY" .venv >/dev/null || die "uv venv failed"
    elif ! "$PY" -m venv .venv >/dev/null 2>&1; then
        rm -rf .venv
        # Debian / Ubuntu ship venv as a separate package (python3.X-venv)
        PYVER=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
        if has apt-get; then
            warn "python$PYVER-venv is missing, installing it"
            pkg_install "" "python$PYVER-venv" || true
        fi
        if ! "$PY" -m venv .venv >/dev/null 2>&1; then
            rm -rf .venv
            ensure_uv || die "Could not create a virtual environment with $PY (install python$PYVER-venv)"
            "$UV" venv --seed --python "$PY" .venv >/dev/null || die "uv venv failed"
        fi
    fi
fi
venv_ok || die "the virtual environment in $ROOT/.venv has no working pip"
.venv/bin/python -m pip install -q --disable-pip-version-check --upgrade pip || die "pip upgrade failed"
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt || die "installing requirements.txt failed (network?)"
ok "packages installed in $ROOT/.venv"

# ---------------------------------------------------------------- 4. Node.js (optional)
# the app uses npm to install agent CLIs with one click
if has npm; then ok "Node.js: $(node --version)"; else
    warn "Node.js not found. Optional: install it (https://nodejs.org) to add Claude Code / Codex / Gemini CLI from the app."
fi

# ---------------------------------------------------------------- 5. Start
if [ -n "$NEONEXUS_NO_START" ]; then say "Installed (start skipped). Start: sh \"$ROOT/council.sh\""; exit 0; fi

# the port as run.py sees it (config.toml + config.local.toml + AGENTCHATTR_PORT)
WEB_PORT=$(.venv/bin/python -c "import config_loader as c; print('PORT', c.load_config()['server']['port'])" 2>/dev/null | sed -n 's/^PORT //p' | tail -1)
[ -n "$WEB_PORT" ] || WEB_PORT=8300
URL="http://127.0.0.1:$WEB_PORT"
http_ok() {
    if has curl; then curl -s -m 2 -o /dev/null "$URL/"
    else .venv/bin/python -c "import sys,urllib.request
try: urllib.request.urlopen(sys.argv[1], timeout=2)
except Exception: sys.exit(1)" "$URL/" 2>/dev/null
    fi
}

say "Starting NEONEXUS"
mkdir -p data
LOG="$ROOT/data/server.log"
if has tmux; then
    COUNCIL_NO_OPEN=1 sh council.sh || die "the room did not start, see $LOG"
elif ! http_ok; then
    nohup .venv/bin/python run.py > "$LOG" 2>&1 &
fi
i=0; while [ $i -lt 60 ] && ! http_ok; do sleep 0.5; i=$((i+1)); done
if ! http_ok; then
    [ -f "$LOG" ] && tail -20 "$LOG" >&2
    die "the server did not answer at $URL. Log: $LOG"
fi

if [ "$OS" = "Darwin" ]; then open "$URL"
elif has xdg-open && { [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; }; then xdg-open "$URL" >/dev/null 2>&1 || true
fi
say "Done. NEONEXUS is at $URL"
echo "  Next: open 'Connect AI' in the app to add your subscriptions, API keys or local models."
echo "  Start again later: sh \"$ROOT/council.sh\"     Stop: sh \"$ROOT/council.sh\" stop"
