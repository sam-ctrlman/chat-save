---
description: "Save this conversation as text to <notes>/conversations/<YYYY-MM-DD-HHMMSS>-<name>[-save-N].md (auto folder + auto name; -n = no date-time)"
argument-hint: "[-n|--no-stamp] [dest folder, e.g. ~/Documents or ~/Documents/work2]"
---

Save the current conversation with the `chat-save` tool. Use exactly these Bash calls, nothing else:

1. `echo chat-save-$(date +%s%N)` and note the printed nonce.
2. In a **separate** call: `grep -l <nonce> ~/.claude/projects/*/*.jsonl` (one path; its file name without `.jsonl` is the session uuid). Never guess the uuid from the newest file.
3. `chat-save --session <uuid> --cwd "$PWD" $ARGUMENTS`

Then show the user the `[ok] saved <path>` line (or the `[error]` line). Do NOT improvise steps the tool does not perform: the tool picks the folder and the name.

- No argument, but the project's `.claude/CLAUDE.md` has `notes-dir: <path>` (relative = from the project root,
  e.g. the /memlayout `docs/notes`) → pass that absolute path as the folder: `<path>/conversations/`.
  At a /memlayout workspace root (has `docs/BOARD.md` + `docs/notes/`) → pass `<ws>/docs/notes`.
- Otherwise no argument → `~/Documents/<workspace>[/<project>]/conversations/` (from the current directory, `project/` dropped).
- `$ARGUMENTS` = a folder → `<folder>/conversations/`.
- The name is `<YYYY-MM-DD-HHMMSS>-<title>.md`: the save time, then the session name (/rename) or auto title; an existing file is never overwritten (`-save-1`, `-save-2`, …).
- `-n` / `--no-stamp` in `$ARGUMENTS` → `<title>.md` (no date-time). Pass it through as is.
