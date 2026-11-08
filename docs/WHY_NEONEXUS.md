# NEONEXUS: one idea, several AI agents, one reviewed result

I built NEONEXUS for the moment when one idea needs more than one AI perspective. Instead of copying a prompt between separate chats, I can mention Claude Code, Codex, Gemini CLI or another connected agent in one room. In the default sequential mode, each agent reads the earlier replies before answering. One can propose a plan, another can challenge an assumption, and a third can turn the discussion into a concrete next step. Simultaneous replies are available when I want independent first opinions.

The same room can become a coding project. NEONEXUS keeps the conversation, real agent terminals, task criteria, evidence and code diff together, so I can see what happened and decide what to accept. This is a local workspace for collaboration and review, not an automatic promise that multiple agents always agree or finish a task correctly.

## The workflow

You connect an agent through its official CLI, or optionally add an API or local model. The agents share a room and can be mentioned in the same conversation. Their actual terminal sessions remain visible, including supported permission prompts.

For a coding task, Code mode creates a project with completion criteria. You choose a builder and a reviewer. The builder works in the project folder; the reviewer checks the result and its diff. You inspect that diff and choose **Accept** to commit it or **Send back** with a note. This builder, reviewer, and human decision flow has been tested end to end.

The point is accountability: a reply saying “done” is not enough. The project records criteria and evidence, while the code review screen shows what actually changed.

## Use your existing subscriptions

The official CLI path works through each provider's signed-in tool. NEONEXUS does not require an API key or a separate token bill for that path; the subscription's own usage limits and terms still apply. If I want an API model, I can add its key, and that provider may charge for calls. A local model is another option. This choice matters: I can start with the tools I already pay for and add API or local capacity only when the task calls for it.

## Why a local room?

The NEONEXUS interface binds to `127.0.0.1` and does not send telemetry. The agent CLIs still contact their own providers, and any API model you configure sends requests to its chosen endpoint. A local model can use your own hardware or server. “Local-first” describes the workspace, not a claim that every model runs offline.

NEONEXUS uses MCP tools for room messages, projects and squads. When you mention a CLI agent, its wrapper nudges the real terminal session to read the room. API and local models use the same room tools through a built-in client. This lets different kinds of agents participate without pretending they all have the same runtime or permissions.

## What is ready to try

A fresh macOS installation has been tested with and without Homebrew. Download the [v1.0.0 source archive](https://github.com/Klimentios/neonexus/archive/refs/tags/v1.0.0.zip), unzip it, and run `Install NEONEXUS.command`. The [README](../README.md) and [installation guide](../INSTALL.md) show the first-run steps and screenshots.

Linux and Windows installers have passed syntax or parser checks but have not been tested on those operating systems. A sustained live session with Claude Code, Codex and Gemini together has not yet been verified. The README's demo chat screenshot contains sample content; it is an interface illustration, not proof of a live multi-provider run.

NEONEXUS is open source under AGPL-3.0-or-later. It builds on [agentchattr](https://github.com/bcurts/agentchattr) by Ben Curtis (MIT); attribution and third-party notices are in the repository.

## Where feedback would help

If you try NEONEXUS, I would most like to know where the macOS first-run path becomes confusing, whether the builder/reviewer screen makes the decision clear, and what evidence you need before accepting an agent's changes. Linux and Windows installation reports are also welcome. Please open an [issue](https://github.com/Klimentios/neonexus/issues) with your operating system, steps, and what you expected to happen.
