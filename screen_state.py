"""What an agent's CLI screen says about its state — one place for the server
(approval cards, badges), the wrapper (when it may type) and squads (briefing).

Rules learnt the hard way:
  * A permission / folder-trust question counts only near the bottom of the screen
    AND with its answer menu under it ("❯ 1. Yes", "> Yes, I trust…"). An agent
    writing "this requires approval" in a reply is not a prompt.
  * Quota and sign-in problems count only as the CLI's own status lines, which start
    with its marker (⚠ ■ ✗ …) or "Error", near the bottom — not an agent quoting them.
"""

from __future__ import annotations

import re

ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")

PROMPT_RE = re.compile(
    r"(?:Do you want to proceed\?|Would you like to (?:run|apply)|Allow access to this file\?"
    r"|Run this command\?|Action Required|Press enter to confirm"
    r"|Do you want to (?:make this edit|create|allow)|requires approval|Allow (?:once|execution)"
    r"|Do you trust (?:the files|the contents|this folder)|Yes, I trust this folder"
    r"|Is this a project you created or one you trust)",
    re.I)
OPTION_RE = re.compile(
    r"^\s*(?:[❯>›●▶]\s*)?(?:\d+[.)]\s*)?(?:yes|no|allow|deny|don't|always|trust|approve|reject|cancel)\b",
    re.I)

_MARKER = r"^\s*(?:[⚠■✗×✘!⎿]\s*|error\b[:\s]*)"
QUOTA_RE = re.compile(
    _MARKER + r".*(?:Individual quota reached|You've hit your usage limit|usage limit reached"
    r"|(?:5-hour|weekly|session) limit reached|Quota exceeded|out of (?:credits|quota))", re.I)
SIGNIN_RE = re.compile(
    _MARKER + r".*(?:access token could not be refreshed|Please sign in again|Not logged in"
    r"|Invalid API key|Please (?:log|sign) in)", re.I)
# whole-screen setup dialogs (the CLI shows only this), no marker needed
SETUP_RE = re.compile(r"How would you like to authenticate|Enter Gemini API Key|Please enter your Gemini API key", re.I)

TAIL = 16


def clean(screen: str) -> list[str]:
    return [line.rstrip() for line in ANSI_RE.sub("", screen or "").splitlines() if line.strip()]


def prompt_line(screen: str) -> int:
    """Index (in clean(screen)) of a question waiting for the human, or -1."""
    lines = clean(screen)
    start = max(0, len(lines) - TAIL)
    for i in range(len(lines) - 1, start - 1, -1):
        if PROMPT_RE.search(lines[i]):
            window = lines[max(0, i - 3):i + 9]
            if any(OPTION_RE.match(x) for x in window):
                return i
            return -1  # the phrase without a menu: prose, not a prompt
    return -1


def waiting_for_human(screen: str) -> bool:
    return prompt_line(screen) >= 0


def _last(screen: str, regex: re.Pattern, tail: int = 10) -> str:
    lines = clean(screen)[-tail:]
    for i in range(len(lines) - 1, -1, -1):
        if regex.search(lines[i]):
            return " ".join(x.strip() for x in lines[i:i + 2])[:240]
    return ""


def quota_hit(screen: str) -> str:
    return _last(screen, QUOTA_RE)


def signin_needed(screen: str) -> str:
    return _last(screen, SIGNIN_RE) or _last(screen, SETUP_RE)
