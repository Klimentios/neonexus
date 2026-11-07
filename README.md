# <img src="static/neonexus-mark.svg" alt="" width="34"> NEONEXUS

**One room for all your AIs.** Claude, ChatGPT / Codex, Gemini and any other model work together
in one chat, on your computer, with the subscriptions you already pay for. You talk to all of them
at once or one by one, by text or by voice, watch their real terminals, hand them projects with
clear "done" criteria, and edit the code they write in a full VS Code — all in one window.

![macOS](https://img.shields.io/badge/macOS-supported-111) ![Linux](https://img.shields.io/badge/Linux-supported-111) ![Windows](https://img.shields.io/badge/Windows-room%20%26%20chat-555) ![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-1f3b73) ![Languages](https://img.shields.io/badge/UI-12%20languages-1f3b73)

![Claude, Codex and Gemini building and reviewing a CLI together](docs/screenshots/room.png)

<p>
<img src="docs/screenshots/projects.png" width="49%" alt="Projects with done criteria and evidence">
<img src="docs/screenshots/connect.png" width="49%" alt="Connect AI: subscriptions, API keys, local models">
<img src="docs/screenshots/cyberpunk.png" width="49%" alt="The Breach cyberpunk theme">
<img src="docs/screenshots/languages.png" width="49%" alt="The interface in Japanese">
</p>

## Why

Every AI is good at something different. Today you copy text between their apps. NEONEXUS puts
them in one room: they read the same conversation, answer each other, split the work, review each
other and report back — and you stay in charge.

- **Your subscriptions, not API bills.** Agents run the official CLIs — Claude Code, Codex,
  Gemini (Antigravity) CLI, Qwen Code, Copilot CLI — signed in with your own accounts.
- **Or any model you like.** Add an API key (OpenAI, Anthropic, OpenRouter, Gemini, Groq,
  DeepSeek, Mistral, xAI, any OpenAI-compatible URL) or a local model (Ollama, LM Studio,
  llama.cpp, vLLM, your own GPU server) from **Connect AI**. Keys never leave your computer except
  to that provider.
- **Local and private.** Everything runs on `127.0.0.1`. No account, no cloud, no telemetry.

## What you get

| | |
|---|---|
| **Code mode** | One button: write a task, pick who builds and who reviews. NEONEXUS makes the folder, a project and a channel; the builder codes, the reviewer checks the diff, and you see every change beside VS Code — **Accept** commits it, **Send back** returns it with your note. |
| **Team chat** | One room, channels, @mentions wake an agent. Mention several and they answer **one after another**, each reading the previous answers (or all at once — your choice in Settings). A loop guard stops endless agent-to-agent chatter. |
| **Agent terminals** | See every agent's own CLI side by side, live. Type into it, press keys, **Allow / Deny** its permission prompts with one click. |
| **Projects** | A goal, criteria for "done", progress. Agents tick criteria with evidence; you accept, reopen, edit or delete. Drag an agent onto a project to add it. |
| **Squads** | A lead agent raises numbered sub-agents, each in its own git worktree and branch; they report, the lead merges. |
| **Code** | A full VS Code (open-source code-server) inside the app on the agents' folder — extensions, terminal, git, search. Fetched once in the background (about 200 MB); the built-in editor works meanwhile. |
| **Voice** | Talk to the whole team or to each agent in turn; live transcription; answers read aloud. |
| **Connect AI** | One screen to add subscription CLIs (one-click install, one-click "Add to team"), API keys, local models, or connect other apps over MCP. |
| **Honest states** | Online, working, waiting for your OK, out of quota (with the date it comes back), signed out (with a **Sign in again** button) — read from the agent's real screen, never guessed. |
| **Safe by default** | Agents ask before running commands. "Full access" is an explicit per-agent switch. |
| **Themes** | Clean (light) by default; Breach and Blackwall for the cyberpunk look. |
| **12 languages** | English, Русский, 中文, Español, Français, Deutsch, Português, 日本語, 한국어, Türkçe, العربية, हिन्दी — picked from your system, switchable in Settings. Agents answer in the language you write in. |

## Install — one click

| System | How |
|---|---|
| **macOS** | Download, unzip, double-click **`Install NEONEXUS.command`** (if macOS blocks it: right-click → Open). |
| **Linux** | `sh install.sh` |
| **Windows 10/11** | Double-click **`install.bat`** (SmartScreen: More info → Run anyway). |

The installer adds only what is missing (Python, tmux), keeps its Python packages inside the
folder, starts the room and opens **http://127.0.0.1:8300**. Then press **Connect AI** and add your
first AI. Details, start / stop and uninstall: [INSTALL.md](INSTALL.md).

> **Tested on macOS** (with and without Homebrew). The Linux and Windows installers are written and
> syntax-checked but have not been run on those systems yet — reports welcome.
> **Windows:** the room, chat, projects, Connect AI and voice; live agent terminals, squads and
> Allow / Deny need tmux, so they are macOS / Linux only for now. Live agent terminals,
> squads and Allow / Deny need tmux, so they are macOS / Linux only for now.

## How it works

```
 you ─┬─ browser UI (127.0.0.1:8300) ─┐
      │                               ├─ room server (FastAPI) ── MCP (127.0.0.1:8200/8201)
      └─ voice / Code tab             │                              ▲
                                      │      ┌───────────────────────┴──────────┐
                                      └──────┤ each agent: its official CLI in a │
                                             │ terminal + a small wrapper that   │
                                             │ wakes it on @mention              │
                                             └───────────────────────────────────┘
```

Agents join the room through MCP tools (`chat_read`, `chat_send`, projects, squads). When you
@mention an agent, its wrapper types a short nudge into its terminal; the agent reads the room and
answers. API and local models run through a built-in client that speaks the same tools.

## Safety

- Everything listens on `127.0.0.1` only. The browser UI uses a per-start session token, and
  requests from other host names or other sites' pages are refused (no DNS-rebinding or
  cross-site access to the room or its terminal).
- Agents run with their CLI's own permission system. By default they **ask** before commands;
  you answer from the UI. **Full access** (`--dangerously-skip-permissions` and equivalents) exists,
  is off, and is set per agent by you.
- API keys are stored in `data/secrets.json` (owner-only permissions) and sent only to the provider
  you added.
- Text typed into agent terminals is stripped of control characters; agent-made images and
  links can't run scripts in the room.
- The Code tab's VS Code is open-source code-server, downloaded once from its GitHub release and
  checked against a pinned SHA-256; it runs on 127.0.0.1 with its own password.
- Nothing is sent anywhere else: no telemetry, no update pings unless you configure a release
  repository.

## Folders

| What | Where |
|---|---|
| App, its Python environment, chat history, settings | the folder you installed into (`data/`) |
| Agents' shared workspace (Code tab, projects, squads) | `~/NEONEXUS/workspace` |
| Chat-only agents' empty folders | `~/NEONEXUS/chats/…` |

Change them in `config.local.toml`:

```toml
[paths]
workspace = "~/code/my-project"
```

## Develop

```bash
.venv/bin/python -m unittest discover -s tests     # test suite
cd tools/web-workspace && npm ci && npm run build   # rebuild the editor / hologram bundles
```

API reference: [API.md](API.md). The original agentchattr guide (launchers, advanced
configuration, architecture): [docs/agentchattr-guide.md](docs/agentchattr-guide.md).

## Licence

NEONEXUS © 2026 Kliment — [GNU AGPL-3.0-or-later](LICENSE). Free to use, study, change and share;
if you distribute a modified version or offer it as a network service, publish your source under
the same licence. Commercial licences without these terms: contact the author.

Built on [agentchattr](https://github.com/bcurts/agentchattr) by Ben Curtis (MIT,
[LICENSE-agentchattr](LICENSE-agentchattr)). Third-party components: [NOTICE.md](NOTICE.md).
Product names belong to their owners; NEONEXUS is not affiliated with Anthropic, OpenAI or Google.
