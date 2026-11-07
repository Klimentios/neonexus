#!/usr/bin/env sh
# NEONEXUS: one command starts the room and every agent whose CLI is installed.
#   sh council.sh          start everything, open the room
#   sh council.sh status   what is running
#   sh council.sh stop     stop everything
#   sh council.sh reset    stop + kill a stuck tmux server
#   sh council.sh attach gemini   look into an agent's terminal (Ctrl+B, D to leave)
#   sh council.sh start-one codex start one agent (the room's Settings use it after a change)
# Agents ask before commands by default ("ask"); "full" access is opt-in per agent in Settings.
# Everything here is scoped to this install folder: a second copy on the same machine has its
# own tmux sockets (data/tmux), its own ports (config) and is never stopped by this one.
cd "$(dirname "$0")" || exit 1
unset TMUX
ROOT="$(pwd)"
ROOT_P="$(pwd -P)"
has() { command -v "$1" >/dev/null 2>&1; }

# ports from config.toml + config.local.toml + AGENTCHATTR_* env, exactly as run.py sees them
PORTS=$(.venv/bin/python -c 'import config_loader as c; k = c.load_config(); print("PORTS", k["server"]["port"], k["mcp"]["http_port"], k["mcp"]["sse_port"])' 2>/dev/null | sed -n 's/^PORTS //p' | tail -1)
if [ -n "$PORTS" ]; then
    WEB_PORT=$(echo "$PORTS" | cut -d' ' -f1)
    MCP_HTTP_PORT=$(echo "$PORTS" | cut -d' ' -f2)
    MCP_SSE_PORT=$(echo "$PORTS" | cut -d' ' -f3)
else
    WEB_PORT=$(sed -n 's/^port *= *\([0-9][0-9]*\).*/\1/p' config.toml | head -1)
    MCP_HTTP_PORT=$(sed -n 's/^http_port *= *\([0-9][0-9]*\).*/\1/p' config.toml | head -1)
    MCP_SSE_PORT=$(sed -n 's/^sse_port *= *\([0-9][0-9]*\).*/\1/p' config.toml | head -1)
fi
WEB_PORT=${WEB_PORT:-8300}; MCP_HTTP_PORT=${MCP_HTTP_PORT:-8200}; MCP_SSE_PORT=${MCP_SSE_PORT:-8201}
URL="http://127.0.0.1:$WEB_PORT"

# Subscriptions only: with no API keys in the environment the CLIs can only use
# their account logins (Claude: claude.ai, Codex: ChatGPT, Gemini: Google).
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN OPENAI_API_KEY CODEX_API_KEY \
      GEMINI_API_KEY GOOGLE_API_KEY GOOGLE_GENAI_USE_VERTEXAI MINIMAX_API_KEY
# private tmux socket dir per install: other shells (sandboxes, `!` commands) and other
# installs can't kill or replace the agents' tmux servers
export TMUX_TMPDIR="$ROOT/data/tmux"
mkdir -p "$TMUX_TMPDIR"
TMUX_SOCKDIR="$TMUX_TMPDIR/tmux-$(id -u)"
# The wrappers themselves run on a second tmux server. Each wrapper attaches to its
# agent's session; doing that from inside the same server makes it render itself
# and hang (that was the "tmux freezes" bug). The -L name lives inside TMUX_TMPDIR,
# so it is already per install (the app's Python code uses the same name).
WRAP="tmux -L council-wrappers"
AGENTS="claude codex gemini claudechat gptchat geminichat"

# HTTP probe: curl if present, else Python (minimal Linux images have no curl)
http_ok() {  # http_ok <timeout seconds>
    if has curl; then curl -s -m "${1:-3}" -o /dev/null "$URL/"
    else .venv/bin/python -c "import sys,urllib.request
try: urllib.request.urlopen(sys.argv[1], timeout=float(sys.argv[2]))
except Exception: sys.exit(1)" "$URL/" "${1:-3}" 2>/dev/null
    fi
}

# --- process scoping: only processes of THIS install folder -----------------
pid_cwd() {
    if [ -e "/proc/$1/cwd" ]; then readlink "/proc/$1/cwd" 2>/dev/null
    elif has lsof; then lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
    fi
}
# pids whose command line matches the regex and whose working folder is this install
own_pids() {
    for pid in $(pgrep -f "$1" 2>/dev/null); do
        [ "$pid" = "$$" ] && continue
        cwd=$(pid_cwd "$pid")
        if [ "$cwd" = "$ROOT" ] || [ "$cwd" = "$ROOT_P" ]; then echo "$pid"; fi
    done
}
# tmux servers/clients of this install: holders of our sockets, or tmux started from here
tmux_pids() {
    {
        if has lsof && [ -d "$TMUX_SOCKDIR" ]; then
            for s in "$TMUX_SOCKDIR"/*; do [ -S "$s" ] && lsof -t "$s" 2>/dev/null; done
        fi
        own_pids '(^|/)tmux( |$)'
    } | sort -u
}
# agent CLIs (e.g. codex -c mcp_servers.agentchattr...) whose parent is one of our tmux servers
agent_cli_pids() {
    tp=" $(tmux_pids | tr '\n' ' ') "
    for pid in $(pgrep -f "mcp_servers.agentchattr" 2>/dev/null); do
        ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        case "$tp" in *" $ppid "*) echo "$pid" ;; esac
    done
}
# the wrapper process itself (the tmux server that launched it carries the same command line)
wrapper_running() {
    for pid in $(own_pids "wrapper.py $1( |\$)"); do
        case "$(ps -o comm= -p "$pid" 2>/dev/null)" in *tmux*) ;; *) return 0 ;; esac
    done
    return 1
}
kill_pids() {  # kill_pids [-9] pid...
    sig=""; [ "$1" = "-9" ] && { sig="-9"; shift; }
    [ -n "$*" ] && kill $sig "$@" 2>/dev/null
    return 0
}
kill_scoped() {  # wrappers, provider configs, agent CLIs of this install
    kill_pids $1 $(own_pids "wrapper.py ($(echo "$AGENTS" | tr ' ' '|'))") \
                 $(pgrep -f "$ROOT/data/provider-config" 2>/dev/null) \
                 $(agent_cli_pids)
}

# only the processes listening on our ports, never other run.py scripts on the machine
port_pids() {
    if has lsof; then
        lsof -t -iTCP:"$WEB_PORT" -iTCP:"$MCP_HTTP_PORT" -iTCP:"$MCP_SSE_PORT" -sTCP:LISTEN 2>/dev/null
    elif has fuser; then
        fuser "$WEB_PORT/tcp" "$MCP_HTTP_PORT/tcp" "$MCP_SSE_PORT/tcp" 2>/dev/null
    fi
}
kill_server() { kill_pids $1 $(port_pids); }

stop_all() {
    cli=$(agent_cli_pids)
    $WRAP kill-server 2>/dev/null
    for a in $AGENTS; do
        tmux kill-session -t "agentchattr-$a" 2>/dev/null
    done
    kill_pids $cli
    kill_scoped
    kill_server
    sleep 1
}

status() {
    echo "Server:"
    if has lsof; then
        lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ":($WEB_PORT|$MCP_HTTP_PORT|$MCP_SSE_PORT) " | awk '{print "  " $1 " pid " $2 " " $9}'
    fi
    if http_ok 3; then echo "  web $URL answers"; else echo "  web $URL not answering"; fi
    echo "Agents:"
    for a in $AGENTS; do
        if wrapper_running "$a"; then echo "  $a: running"; else echo "  $a: stopped"; fi
    done
}

case "$1" in
    stop)   stop_all; echo "Council stopped."; exit 0 ;;
    attach) exec tmux attach -t "agentchattr-${2:-claude}" ;;
    # first run: each CLI waits for a human once (theme, folder trust, Google sign-in)
    setup)  for a in claude claudechat codex gptchat gemini geminichat; do
                echo ""
                echo "=== $a: answer any question on screen (theme, trust folder: yes, Gemini: Sign in with Google)."
                echo "    When it shows an empty prompt, press Ctrl+B then D to go to the next agent."
                printf "    Enter to open %s... " "$a"; read _
                tmux attach -t "agentchattr-$a"
            done
            echo ""; echo "Setup done."; exit 0 ;;
    # a stuck tmux server makes every tmux command hang, so kill this install's tmux
    # processes by pid (never every tmux on the machine) and drop only our sockets
    reset)  cli=$(agent_cli_pids)
            kill_pids -9 $(tmux_pids)
            rm -f "$TMUX_SOCKDIR/default" "$TMUX_SOCKDIR/council-wrappers" 2>/dev/null
            kill_pids -9 $cli
            kill_scoped -9
            kill_server -9; echo "Council reset."; exit 0 ;;
    status) status; exit 0 ;;
esac

# a busy server may miss one probe; restart only after three misses in a row
web_alive() {
    for _ in 1 2 3; do
        http_ok 3 && return 0
        sleep 2
    done
    return 1
}

if ! web_alive; then
    kill_server
    mkdir -p data
    nohup .venv/bin/python run.py > data/server.log 2>&1 &
    i=0
    while [ "$i" -lt 40 ] && ! http_ok 1; do
        sleep 0.5; i=$((i + 1))
    done
    if ! http_ok 2; then
        echo "Server did not start, see $ROOT/data/server.log:"
        tail -20 data/server.log
        exit 1
    fi
fi
echo "Server: $URL"

# model/effort chosen in the UI (data/agent_models.json), as shell-quoted CLI flags
model_flags() {
    .venv/bin/python council_ext.py flags "$1" 2>/dev/null | while IFS= read -r f; do printf " '%s'" "$f"; done
}

start_agent() {
    name="$1"; shift
    if wrapper_running "$name"; then
        echo "  $name: already running"
        return 1
    fi
    if ! .venv/bin/python council_ext.py installed "$name" 2>/dev/null; then
        echo "  $name: CLI not installed, skipped (Connect AI in the browser can install it)"
        return 1
    fi
    if ! has tmux; then
        echo "  $name: needs tmux, skipped (install tmux to run agent terminals)"
        return 1
    fi
    $WRAP new-session -d -s "council-$name" "unset TMUX; .venv/bin/python wrapper.py $name $*$(model_flags "$name")"
    # keep the wrapper's screen in a log: launchd starts have no terminal to look at
    mkdir -p data/logs
    $WRAP pipe-pane -o -t "council-$name" "cat >> '$ROOT/data/logs/$name.log'"
    echo "  $name: started"
}

# the room's own MCP server is injected by the wrapper; skip a "council" entry in
# ~/.codex/config.toml (added if you connect the Codex app via council_bridge), or Codex would
# see every chat tool twice
NO_BRIDGE="-c mcp_servers.council.enabled=false"
# Codex asks before every MCP call by default; pre-approve only the room's own chat tools
CHAT_OK="-c mcp_servers.agentchattr.default_tools_approval_mode=\"approve\""

# CLI agents the user added from Connect AI ("Add to team"): they live in config.local.toml
EXTRA=$(.venv/bin/python -c 'import tomllib,sys
try: a=tomllib.load(open("config.local.toml","rb")).get("agents",{})
except Exception: a={}
print(" ".join(n for n,c in a.items() if isinstance(c,dict) and c.get("command") and c.get("type")!="api"))' 2>/dev/null)

# start-one NAME: the same start_agent call and flags as the full start below, one agent only
if [ "$1" = "start-one" ]; then
    case " $EXTRA " in *" $2 "*) start_agent "$2"; exit 0 ;; esac
    case "$2" in
        claude)     start_agent claude ;;
        codex)      start_agent codex $NO_BRIDGE $CHAT_OK ;;
        gemini)     start_agent gemini --settings "$ROOT/agy-room-permissions.json" ;;
        claudechat) start_agent claudechat "--tools '' --allowedTools mcp__agentchattr" ;;
        gptchat)    start_agent gptchat --sandbox read-only $NO_BRIDGE $CHAT_OK ;;
        geminichat) start_agent geminichat --mode plan --settings "$ROOT/agy-room-permissions.json" ;;
        *)          echo "start-one: unknown agent '$2' (one of: $AGENTS)"; exit 2 ;;
    esac
    exit 0
fi

# workers: edit files inside the lab folder; permission flags (ask / full access,
# chosen per agent in the UI) come from council_ext.py with the model flags
start_agent claude
start_agent codex $NO_BRIDGE $CHAT_OK
# Antigravity asks before every MCP call; this session-only file pre-approves the room's chat tools
AGY_OK="--settings $ROOT/agy-room-permissions.json"

# both agy agents read one global MCP file; give a fresh one time to load its token
start_agent gemini $AGY_OK && sleep 12

# chat-only companions: no file/shell tools (Gemini Chat runs agy in read-only plan mode)
[ -z "$COUNCIL_NO_CHAT" ] && {
    start_agent claudechat "--tools '' --allowedTools mcp__agentchattr"
    start_agent gptchat --sandbox read-only $NO_BRIDGE $CHAT_OK
    start_agent geminichat --mode plan $AGY_OK
}

for extra in $EXTRA; do start_agent "$extra"; done

echo ""
echo "Folder:  $(.venv/bin/python -c 'import config_loader as c; print("WS", c.load_config()["paths"]["workspace"])' 2>/dev/null | sed -n 's/^WS //p' | tail -1)"
echo "Agents:  sh $ROOT/council.sh attach claude | codex | gemini"
# a watchdog (launchd / cron) may run this again; only an interactive start opens the browser
if [ -z "$COUNCIL_NO_OPEN" ]; then
    if command -v open >/dev/null 2>&1 && [ "$(uname -s)" = Darwin ]; then open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true; fi
fi
exit 0
