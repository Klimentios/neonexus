# Contributing to NEONEXUS

Thanks for helping improve NEONEXUS. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before
changing a subsystem. Keep changes focused and describe the user-visible result in your pull request.

## Local checks

Create a Python environment and install the repository requirements, then run:

```sh
TMUX_TMPDIR=/tmp/nx-tests .venv/bin/python -m unittest discover -s tests
```

Use [INSTALL.md](INSTALL.md) for setup details. Avoid starting a second copy on ports already used by
an existing room.

## Interface text

NEONEXUS has 12 UI languages. Add a new string as `t('English', 'Русский')` in the interface, add
the English source to `static/i18n/source.json`, and update every `static/i18n/<lang>.js` translation.
Check layout in both light and dark themes, including Arabic right-to-left.

## Commits and pull requests

Use short imperative commit subjects, for example `Clarify Windows install status`. Explain what
changed, how you checked it, and what remains unverified. Do not include API keys, session tokens,
private chats, or real project data in issues, screenshots, or test fixtures.

Contributions to NEONEXUS are distributed under [AGPL-3.0-or-later](LICENSE). Existing agentchattr
material retains its MIT licence and attribution in [LICENSE-agentchattr](LICENSE-agentchattr) and
[NOTICE.md](NOTICE.md).
