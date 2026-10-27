---
description: "TODO: chat-save — describe what this slash command does"
argument-hint: "[run|install|uninstall]"
---

Run `chat-save $ARGUMENTS` from the user's current directory using the Bash tool.

`chat-save` is a Python tool at `~/scripts/chat-save/bin/chat-save.py` (symlinked to `~/.local/bin/chat-save`). This slash command file is at `~/scripts/chat-save/commands/chat-save.md` (symlinked to `~/.claude/commands/chat-save.md`).

Actions:

- **`chat-save`** or **`chat-save run`** — TODO: the workflow this tool automates (not implemented yet — edit `cmd_run()` in the script).
- **`chat-save install`** — create both symlinks (bin + Claude command). Idempotent.
- **`chat-save uninstall`** — remove both symlinks. Idempotent.

After it returns, surface the `[ok]` / `[error]` / `[notice]` log lines to the user. Do NOT improvise steps the tool does not perform — the tool owns its workflow.

Pass through `$ARGUMENTS` verbatim. Valid args: `run`, `install`, `uninstall`, or empty (defaults to `run`).
