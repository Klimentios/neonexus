"""Council bridge — puts the chat room into apps that only speak stdio MCP.

Claude.app (chat tab) and the Codex app launch this as a local MCP server.
Each tool call is forwarded to agentchattr's streamable-http MCP endpoint, with
`sender` filled in as this app's identity (COUNCIL_SENDER, e.g. app-claude), so
from a normal chat you can read the room, post into it and @mention agents.

The connection is opened per call: the app may start before the Council server
does, and a restarted server must not leave the app with a dead session.

    COUNCIL_MCP_URL  default http://127.0.0.1:8200/mcp
    COUNCIL_SENDER   default app-claude
"""

import asyncio
import os

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

URL = os.environ.get("COUNCIL_MCP_URL", "http://127.0.0.1:8200/mcp")
SENDER = os.environ.get("COUNCIL_SENDER", "app-claude")

# Room tools that make sense from an outside chat; identity/hat tools stay agent-only.
EXPOSED = {
    "chat_read", "chat_send", "chat_who", "chat_channels", "chat_summary",
    "chat_rules", "chat_propose_job", "chat_job_update", "chat_mission",
    "chat_log_decision", "project_status", "project_create", "project_check", "project_update",
    "squad_status",
}

INSTRUCTIONS = (
    f"You are connected to the Council chat room as '{SENDER}'. The room is a shared chat "
    "with the user and the coding agents Claude, Codex and Gemini (and chat-only models). "
    "Use chat_read to see what is going on (channel 'general' unless told otherwise) and "
    "chat_send to post. Writing @codex, @claude or @gemini in a message wakes that agent; "
    "read the room again afterwards to see its reply. The sender is filled in for you."
)

OFFLINE = "NEONEXUS is not running. Start it with: sh council.sh in its folder (Windows: install.bat)."

server = Server("council", instructions=INSTRUCTIONS)
_schemas: dict[str, dict] = {}


async def _with_room(fn):
    async with streamablehttp_client(URL, timeout=10) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    try:
        result = await _with_room(lambda s: s.list_tools())
    except Exception:
        return []
    tools = []
    for tool in result.tools:
        if tool.name not in EXPOSED:
            continue
        _schemas[tool.name] = tool.inputSchema or {}
        schema = dict(tool.inputSchema or {})
        # sender is ours to set: hide it from the model
        props = dict(schema.get("properties", {}))
        props.pop("sender", None)
        schema["properties"] = props
        schema["required"] = [r for r in schema.get("required", []) if r != "sender"]
        # results are passed through as text content only, so no structured outputSchema
        tools.append(tool.model_copy(update={"inputSchema": schema, "outputSchema": None}))
    return tools


@server.call_tool(validate_input=False)
async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
    if name not in EXPOSED:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    args = dict(arguments or {})
    if "sender" in _schemas.get(name, {}).get("properties", {"sender": 1}):
        args["sender"] = SENDER
    try:
        result = await _with_room(lambda s: s.call_tool(name, args))
    except Exception:
        return [types.TextContent(type="text", text=OFFLINE)]
    return list(result.content)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
