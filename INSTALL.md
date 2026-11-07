# Install NEONEXUS

NEONEXUS runs on your own computer. On macOS, the installer was tested from a fresh clone. It
keeps Python packages inside this folder, starts the room and opens <http://127.0.0.1:8300>
(the port comes from `config.toml`). Linux and Windows install paths need on-device verification.

## macOS

Double-click **`Install NEONEXUS.command`** in Finder (or run `sh install.sh` in Terminal).

If macOS says the file "cannot be opened because it is from an unidentified developer",
right-click it, choose **Open**, then **Open** again. You only need to do this once.

## Linux (Ubuntu, Debian, Fedora, Arch, openSUSE)

```sh
sh install.sh
```

It asks for your `sudo` password when it installs tmux or Python with apt / dnf / pacman / zypper.

## Windows 10 / 11

Double-click **`install.bat`**.

If Windows SmartScreen shows "Windows protected your PC", click **More info**, then
**Run anyway**.

The Windows implementation targets room, chat, projects, Connect AI and voice, with Claude Code /
Codex / Gemini CLI agents in their own windows. These paths have not been run end to end on Windows.
Live agent terminals, squads and Allow / Deny require tmux and are unavailable there for now.

*The Windows installer is checked for syntax (PowerShell parser, pure ASCII for Windows
PowerShell 5.1) but has not yet been run end to end on a Windows machine. Please report problems.*

## What gets installed, and where

| What | Where |
|---|---|
| Python packages (FastAPI, uvicorn, MCP, httpx) | `.venv/` inside this folder |
| Python 3.12, only if no Python 3.11+ is found | macOS: Homebrew, or [uv](https://docs.astral.sh/uv/) in `~/.local/bin` when Homebrew is absent. Linux: the package manager, or uv when its Python is older than 3.11 (e.g. Ubuntu 22.04). Windows: `winget` (python.org link if winget is missing) |
| tmux (agent terminals, squads) | macOS: Homebrew (skipped with a note if Homebrew is absent). Linux: the package manager |
| Room data: chat history, settings, API keys you add | `data/` inside this folder |
| Agents' folders | `~/NEONEXUS/workspace` and `~/NEONEXUS/chats`, created by the app on its first start (change them under `[paths]` in `config.toml` or `config.local.toml`) |

Node.js is optional: with it, **Connect AI** can install the agent CLIs (Claude Code, Codex,
Gemini CLI, ...) for you with one click.

Install only, without starting: `NEONEXUS_NO_START=1 sh install.sh`
(Windows: `set NEONEXUS_NO_START=1` before running `install.bat`).

## Start and stop

macOS / Linux, in this folder:

```sh
sh council.sh           # start the room and every agent whose CLI is installed
sh council.sh status    # what is running
sh council.sh stop      # stop everything
```

Without tmux, `council.sh` starts only the room (no agent terminals).

Windows: run `install.bat` again to start. To stop, end the `python.exe` process whose id the
installer printed (`taskkill /PID <id> /F`; it is also stored in `data\server.pid`) and close the
agent windows.

## Then: Connect AI

Open **Connect AI** in the app:

- **Subscriptions**: Claude Code, Codex, Gemini CLI, Qwen Code, Copilot CLI. One-click install
  (needs Node.js), then sign in once in the agent's own terminal (Agents screen).
- **API key**: OpenAI, Anthropic, OpenRouter, Gemini, Groq, DeepSeek, Mistral, xAI or any
  OpenAI-compatible URL. The key stays in `data/secrets.json` on this computer.
- **Local**: Ollama, LM Studio, llama.cpp, vLLM or your own GPU server.
- **Other apps**: copy the MCP snippet into Claude Desktop, Cursor, VS Code, ...

## Uninstall

1. Stop it: `sh council.sh stop` (Windows: see above).
2. Delete this folder (it holds the app, `.venv` and `data/`).
3. Delete `~/NEONEXUS` if you no longer need the agents' files.

Python, tmux, uv or Node.js installed along the way stay on the system; remove them with the
tool that installed them if you want (`brew uninstall`, `apt remove`, `rm ~/.local/bin/uv`, ...).
