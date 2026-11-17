---
name: chat-save
description: "Save this conversation as text to <notes>/conversations/<YYYY-MM-DD-HHMMSS>-<name>[-save-N].md (auto folder + auto name; -n = no date-time)"
argument-hint: "[-n|--no-stamp] [-a|--anon] [--title <text>] [dest folder, e.g. ~/Documents or ~/Documents/work2]"
disable-model-invocation: true
---

Save the current conversation with the `chat-save` tool. Follow the steps for the calling agent:

### If the calling agent is Antigravity (`agy`)
`Conversation ID` is already present in `<user_information>`. Run this single Bash call:
1. `chat-save --session <Conversation ID> $ARGUMENTS`

### If the calling agent is Claude Code (`claude`)
Use these 3 Bash calls, nothing else:
1. `echo chat-save-$(date +%s%N)` and note the printed nonce.
2. In a **separate** call: `grep -l <nonce> ~/.claude/projects/*/*.jsonl` (one path; its file name without `.jsonl` is the session uuid). Never guess the uuid from the newest file.
3. `chat-save --session <uuid> $ARGUMENTS` (the tool takes the folder from the chat start folder in the transcript; no `--cwd`)

---

Then show the user the `[ok] saved <path>` line (or the `[error]` line). Do NOT improvise steps the tool does not perform: the tool picks the folder and the name.

- No argument, but the project's `.claude/CLAUDE.md` or `.agents/rules/AGENTS.md` has `notes-dir: <path>` (relative = from the project root,
  e.g. the /memlayout `docs/notes`) → pass that absolute path as the folder: `<path>/conversations/`.
  At a /memlayout workspace root (has `docs/BOARD.md` + `docs/notes/`) → pass `<ws>/docs/notes`.
- Otherwise no argument → `~/Documents/<workspace>[/<project>]/conversations/` (from the folder the chat started in, `project/` dropped;
  a start folder under `~/Documents/<x>` → `~/Documents/<x>/conversations/`, never `Documents/Documents`).
- `$ARGUMENTS` = a folder → `<folder>/conversations/`.
- The name is `<YYYY-MM-DD-HHMMSS>-<title>.md`: the save time, then `--title`, the session name (/rename), auto title, or first prompt slug; an existing file is never overwritten (`-save-1`, `-save-2`, …).
- `-n` / `--no-stamp` in `$ARGUMENTS` → `<title>.md` (no date-time). Pass it through as is.
