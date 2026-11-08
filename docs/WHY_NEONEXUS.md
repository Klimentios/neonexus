# Why I built NEONEXUS: one room for several AI coding agents

I use more than one AI coding tool. Each CLI is useful on its own, but separate terminals make it hard to see the full conversation, know which agent is waiting for approval, and review the changes before they become part of a project. I built NEONEXUS to put those steps in one local workspace.

## The workflow

You connect an agent through its official CLI, or optionally add an API or local model. The agents share a room and can be mentioned in the same conversation. Their actual terminal sessions remain visible, including supported permission prompts.

For a coding task, Code mode creates a project with completion criteria. You choose a builder and a reviewer. The builder works in the project folder; the reviewer checks the result and its diff. You inspect that diff and choose **Accept** to commit it or **Send back** with a note. This builder, reviewer, and human decision flow has been tested end to end.

The point is accountability: a reply saying “done” is not enough. The project records criteria and evidence, while the code review screen shows what actually changed.

## Why a local room?

The NEONEXUS interface binds to `127.0.0.1` and does not send telemetry. The agent CLIs still contact their own providers, and any API model you configure sends requests to its chosen endpoint. A local model can use your own hardware or server. “Local-first” describes the workspace, not a claim that every model runs offline.

NEONEXUS uses MCP tools for room messages, projects and squads. When you mention a CLI agent, its wrapper nudges the real terminal session to read the room. API and local models use the same room tools through a built-in client. This lets different kinds of agents participate without pretending they all have the same runtime or permissions.

## What is ready to try

A fresh macOS installation has been tested with and without Homebrew. Download the [v1.0.0 source archive](https://github.com/Klimentios/neonexus/archive/refs/tags/v1.0.0.zip), unzip it, and run `Install NEONEXUS.command`. The [README](../README.md) and [installation guide](../INSTALL.md) show the first-run steps and screenshots.

Linux and Windows installers have passed syntax or parser checks but have not been tested on those operating systems. A sustained live session with Claude Code, Codex and Gemini together has not yet been verified. The README's demo chat screenshot contains sample content; it is an interface illustration, not proof of a live multi-provider run.

NEONEXUS is open source under AGPL-3.0-or-later. It builds on [agentchattr](https://github.com/bcurts/agentchattr) by Ben Curtis (MIT); attribution and third-party notices are in the repository.

## Where feedback would help

If you try NEONEXUS, I would most like to know where the macOS first-run path becomes confusing, whether the builder/reviewer screen makes the decision clear, and what evidence you need before accepting an agent's changes. Linux and Windows installation reports are also welcome. Please open an [issue](https://github.com/Klimentios/neonexus/issues) with your operating system, steps, and what you expected to happen.
