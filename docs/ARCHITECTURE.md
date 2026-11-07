# How NEONEXUS fits together

```
browser (static/) ──HTTP + /ws──► app.py (FastAPI, 127.0.0.1:8300) ◄──MCP 8200/8201── agents
                                     │  stores: messages, rules, jobs, schedules, sessions
                                     │  modules: council_ext · projects · squads · connect · ide · workspace_api
                                     ▼
                     data/<agent>_queue.jsonl ──► wrapper.py ──tmux──► the agent's official CLI
```

- **`run.py`** loads the config (`config_loader`: `config.toml` + `config.local.toml` + `AGENTCHATTR_*`
  env), creates a per-start session token, starts the two MCP servers from `mcp_bridge`
  (streamable HTTP on 8200, SSE on 8201, both on 127.0.0.1) and serves the web UI on 8300.
- **`app.py`** is the hub: message store, rules, jobs, schedules, sessions, the agent `registry`
  (instances and their tokens), the `router` (@mentions → targets, loop guard, turn order) and
  `AgentTrigger`, which appends a wake-up to `data/<agent>_queue.jsonl`. All routes sit behind one
  security middleware (Host, Origin, session token); WebSockets check the same with `ws_allowed`.
- **The browser** (`static/index.html`, `chat.js` from upstream, `shell.js` layout and views,
  `skins.*` themes, `i18n.js` + `locale.js` + `static/i18n/*.js` for 12 languages) gets the token
  from the page and talks REST with `X-Session-Token` plus live events over `/ws`.
- **`mcp_bridge`** gives agents their tools: `chat_*`, `project_*`, `squad_*`. The caller is the
  agent behind the bearer token, never a name it claims.
- **`wrapper.py`** runs one agent: registers it, writes the CLI's MCP config, starts the CLI in a
  tmux session (`wrapper_unix`; `wrapper_windows` on Windows), watches its queue and types a short,
  sanitised nudge; the agent then reads the room and answers through MCP. **`wrapper_api.py`** is
  the same loop for OpenAI-compatible HTTP models (Connect AI → API key / local model).
- **`screen_state.py`** reads an agent's terminal: permission prompts, quota, sign-in. The UI's
  Allow / Deny and the status badges come only from it.
- **`council_ext`**: missions, personas, decisions, per-agent model and access mode (ask / full),
  restart and sign-in. **`projects`**: goals and done criteria, mirrored to
  `<workspace>/.council/`. **`squads`**: sub-agents in git worktrees `<workspace>/.squads/<member>`
  that report, and a lead that merges.
- **`connect.py`**: the Connect AI screen — install CLIs with npm, add API / local agents (keys in
  `data/secrets.json`, mode 600), add an installed CLI to the team.
- **`ide.py`**: downloads a pinned, SHA-256-checked code-server once and runs it on 127.0.0.1:8444;
  the Code tab logs in through a one-shot nonce. **`workspace_api`**: the built-in editor's files
  and terminal, limited to the workspace folder.
- **`council.sh`** starts the room and every agent whose CLI is installed, each in its own tmux
  session under `data/tmux`; `start-one NAME` restarts one.

## Working on it

- Tests: `.venv/bin/python -m unittest discover -s tests`.
- A second instance for experiments: `.venv/bin/python run.py --port 8390 --mcp-http-port 8290
  --mcp-sse-port 8291 --data-dir /tmp/neonexus-dev` with `AGENTCHATTR_NO_AUTOSTART=1`.
- New UI text: write it as `t('English', 'Русский')` in `shell.js`, then add the English string to
  `static/i18n/source.json` and every `static/i18n/<lang>.js`.
- Editor and hologram bundles: `cd tools/web-workspace && npm ci && npm run build`.
