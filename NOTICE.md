# NOTICE

**NEONEXUS** — a local room where your AI agents work together.

Copyright © 2026 Kliment <Klimentioss@gmail.com>. All rights reserved where not granted by the licence below.

NEONEXUS is free software: you can redistribute it and/or modify it under the terms of the
**GNU Affero General Public License version 3** or (at your option) any later version, as published
by the Free Software Foundation. See [LICENSE](LICENSE).

In short: anyone may use, study, change and share it for free. If you distribute a modified version,
or run a modified version as a service other people use over a network, you must publish your
source code under the same licence. Commercial licences without these obligations are available
from the author.

## Based on agentchattr

NEONEXUS started as a fork of [agentchattr](https://github.com/bcurts/agentchattr)
by Ben Curtis, released under the MIT License. The original code keeps that licence and its
copyright notice: see [LICENSE-agentchattr](LICENSE-agentchattr). Everything added or changed
since the fork is © Kliment and licensed under AGPL-3.0-or-later.

## Third-party components

| Component | Licence | Where |
|---|---|---|
| Monaco Editor (Microsoft) | MIT | `static/workspace.bundle.*`, `static/editor.worker.js` |
| xterm.js | MIT | `static/workspace.bundle.js` |
| three.js | MIT | `static/hologram.bundle.js` |
| marked | MIT | `static/marked.min.js` |
| Face geometry from [AI Mirror](https://github.com/yusufk/ai_mirror) | MIT | `static/hologram.bundle.js` |
| Codicons (Microsoft) | CC BY 4.0 | `static/codicon-*.ttf` |
| code-server (Coder) | MIT | downloaded on first use of the Code tab into `data/code-server/`, not bundled |

Full texts: `static/workspace-licenses.txt`, `static/marked.LICENSE.md`, `static/ai-mirror.LICENSE.md`.
Bundles are built from `tools/web-workspace/` (`npm ci && npm run build`).

"Claude", "ChatGPT", "Codex", "Gemini" and other product names belong to their owners. NEONEXUS is
not affiliated with or endorsed by Anthropic, OpenAI, Google or any other provider; it runs their
official command-line tools with the user's own accounts.
