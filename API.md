# NEONEXUS HTTP API

All routes are on `http://127.0.0.1:8300` and need the session token, the same
way the existing `static/*.js` calls do. Live updates arrive over the existing
WebSocket `/ws`.

## UI panel → data

| Panel | Read | Write | Live event (`/ws`) |
|---|---|---|---|
| CHANNELS + unread | existing `settings.channels`, messages | existing | existing |
| AGENTS (name, role, online, avatar) | `GET /api/status` + `GET /api/council/state` → `personas[agent]` | `PUT /api/council/personas/{agent}` | `status`, `council` kind `persona` |
| JOBS // MISSION header | `GET /api/council/state` → `missions[channel]` | `PUT /api/council/missions/{channel}` · `DELETE` | `council` kind `mission` |
| JOBS list with due + checkboxes | `GET /api/jobs?channel=X` → `due`, `checklist[]` | see Jobs below | `job` (`create`/`update`) |
| RULES // AGENT POLICY | `GET /api/rules` → rule has `channel` ("" = all channels) | WS `rule_propose` / `rule_edit` with `scope: "<channel>"` | `rule` |
| DECISION badge / decision log | `GET /api/council/decisions?channel=X` | `POST /api/council/decisions` · `DELETE /api/council/decisions/{id}` | `council` kind `decision` / `decision_delete` |

## Shapes

```jsonc
// mission
{"channel": "orbit", "title": "Project Orbit - MVP", "body": "Deliver a working prototype in 7 days",
 "due": "2026-11-10", "updated_at": 1793695357.5}

// persona (role also changes what the agent is told on every wake-up)
PUT /api/council/personas/claude
{"title": "Architect", "role": "Architect", "avatar": "/uploads/architect.png",
 "color": "#ffd400", "description": "plans and reviews"}

// job (new fields only)
{"id": 1, "title": "Finalize scope", "due": "2026-11-03",
 "checklist": [{"id": 1, "text": "cut analytics", "done": true}]}

// decision
{"id": 3, "text": "MVP = core flow only", "author": "claude", "channel": "orbit",
 "msg_id": 42, "created_at": 1793695357.5}
```

## Jobs

- `POST /api/jobs` — add `"due": "YYYY-MM-DD"` and `"checklist": ["item", ...]`
- `PATCH /api/jobs/{id}` — `due` (`""` clears), `body`, plus the old `status` / `title` / `assignee`
- `POST /api/jobs/{id}/checklist` `{"text": "..."}`
- `PATCH /api/jobs/{id}/checklist/{item}` `{"done": true}` or `{"text": "..."}`
- `DELETE /api/jobs/{id}/checklist/{item}`

"DUE TODAY" / "+5D" are computed in the UI from `due` vs today.

## Decisions

A chat message that starts with `DECISION:` or `РЕШЕНИЕ:` (bold allowed) is
recorded automatically, and the UI can render it with the DECISION badge.
Every decision is also written to `<workspace>/.council/DECISIONS.md`, the
project memory any agent can read.

## Agents (MCP tools)

`chat_job_update` (status, due, add/tick checklist items), `chat_log_decision`,
`chat_mission`. On every wake-up the agent is given its role, the channel
mission and the rules of that channel.

## Model and power per agent

- `GET /api/council/models` → `{agents: {claude: {provider, model, effort}}, options, presets}`;
  empty `model` / `effort` = the CLI's own default
- `PUT /api/council/models/{agent}` `{"model": "opus", "effort": "high"}` or `{"preset": "fast|balanced|max"}`
- `PUT /api/council/models` `{"preset": "..."}` — every agent at once

A change restarts only that agent (a few seconds; the room history stays, the
CLI's own conversation starts fresh). Gemini runs on Antigravity CLI (`agy`):
effort low…max like Claude; its model ids come from `agy models` after sign-in,
so presets keep its default model and only change the effort.

| Preset | Claude | Codex | Gemini |
|---|---|---|---|
| fast | haiku · low | gpt-6-luna · low | default · low |
| balanced | sonnet · medium | gpt-6.1-sol · medium | default · medium |
| max | opus · high | gpt-6-astra · high | default · high |
