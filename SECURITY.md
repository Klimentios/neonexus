# Security policy

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** / private security advisory for this repository, if
available. Do not post exploit details, tokens, private chats, or logs containing secrets in a public
issue. If private reporting is unavailable, open a public issue asking for a private contact route
without describing the vulnerability.

## Scope and expectations

NEONEXUS is designed to bind its room and MCP endpoints to `127.0.0.1`. It uses a session token and
rejects foreign Host and Origin values. Agent CLIs and selected API providers may still send prompts
and code to their own services. Review those providers' policies and the permissions you grant each
agent. Keep the app updated and avoid exposing its local ports to a network.

Security reports are welcome for version 1.0.0. No response-time or fix-time guarantee is claimed.
