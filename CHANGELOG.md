# Changelog

## 1.0.0 — 2026-11-07

### Room
- Channels, mentions, pins, jobs, rules, schedules, sessions, and history export/import.
- Sequential or simultaneous multi-agent replies, with a loop guard.

### Agents
- Live CLI terminals with per-agent restart, status, and supported Allow / Deny prompts.
- 25 MCP tools for chat, projects, and squads; identity comes from each agent's token.
- Stateless MCP connections keep agents connected across room restarts.

### Code
- Code mode: task and Git starting point, builder, reviewer, diff review, then Accept or Send back.
- A built-in editor and an optional embedded code-server, pinned and SHA-256 checked.
- Squads use separate Git worktrees and branches for sub-agents.

### Projects
- Done criteria with evidence, progress, editing, completion and agent assignment.

### Connect AI
- Subscription CLI setup, optional API providers, local OpenAI-compatible models, and MCP snippets.

### Interface
- Clean, Breach and Blackwall themes; 12 languages including Arabic right-to-left.
- Browser speech integration and speech output. A real microphone session remains unverified.

### Safety
- Loopback binding, session token, Host and Origin checks, terminal input sanitization, and no telemetry.
- API keys stored with owner-only permissions and sent to the selected provider.

macOS installation was tested from a fresh clone. Linux and Windows installers have syntax/parser
checks only and still need tests on those systems. See [INSTALL.md](INSTALL.md).

NEONEXUS is based on [agentchattr](https://github.com/bcurts/agentchattr) by Ben Curtis (MIT).
See [LICENSE-agentchattr](LICENSE-agentchattr) and [NOTICE.md](NOTICE.md).
