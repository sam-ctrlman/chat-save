# chat-save

<!-- created by /memlayout 2026-10-30 · board prefix TOOL-CSAVE · workspace tools -->

## Goal
Saves a Claude Code conversation as Markdown to `<notes>/conversations/<name>[-save-N].md`, folder and name picked automatically.

## Users
A developer who runs Claude Code on their own machine and wants this step done the same way every time.

## Scope
- In: the commands in `README.md`, `chat-save install` / `uninstall` (symlinks onto PATH and into `~/.claude`).
- Out (non-goals): anything that needs a server or a network service of its own.

## Depends on / used by
Other tools in the workspace only through their CLI. See `~/tools/docs/PROJECTS.md`.
