# chat-save

**CLI utility and Claude Code skill to export Claude Code sessions into clean, readable Markdown transcripts with automatic naming, project folder routing, provenance headers, and anonymous sharing (`--anon`).**

Claude Code's built-in `/export` command requires manually typing a destination path and filename every time, and raw `.jsonl` session files in `~/.claude/projects/` are cluttered with system reminders, internal metadata, and verbose tool payloads. `chat-save` automatically resolves the active session's title (`/rename` or AI title), routes the file into your project's notes directory, strips system noise, and saves a clean `.md` conversation log without ever overwriting previous saves.

---

## Why Use `chat-save`?

- **Automatic Title & Timestamp Naming:** Picks the session name (`/rename`), automatic AI title, or session UUID and saves as `<YYYY-MM-DD-HHMMSS>-<slug>.md` (or `<slug>.md` with `-n` / `--no-stamp`).
- **Smart Workspace & Project Routing:** Automatically derives the output folder from your session's working directory (`~/Documents/<workspace>/<project>/conversations/` or your project's configured `notes-dir`).
- **Collision-Safe Saving:** Never overwrites an existing transcript — subsequent saves append `-save-1.md`, `-save-2.md`, and so on.
- **Readable Markdown Output:** Keeps your prompts (`❯`), assistant responses (`⏺`), and compact 1-line tool summaries (`⏺ Tool(...)`) while stripping `<system-reminder>` blocks, sidechains, compact summaries, and raw tool output blobs.
- **Anonymous Sharing Mode (`-a` / `--anon`):** Strips local provenance headers (`Directory:`, `Session:`, `Host:`) when exporting a transcript to share externally.
- **Zero External Dependencies:** Pure Python 3 standard library.

---

## Example Saved Markdown Output

### Default Output (with Provenance Header)
```markdown
Conversation: refactor-auth-middleware
Saved: 2026-11-07 14:25
Directory: /home/user/work/project/my-app
Session: 8f9a2c10-4b1e-4d3a-9c7e-123456789abc
Host: workstation-01

❯ Can you inspect the session token middleware and check why expired tokens return 500?

⏺ Read(/home/user/work/project/my-app/src/auth/middleware.ts)

⏺ The `verifyToken()` call throws `TokenExpiredError` before reaching the status handler. Let's catch it and return `401 Unauthorized`.
```

### Anonymous Mode (`chat-save -a`)
Omits `Directory:`, `Session:`, and `Host:` so local filesystem paths and machine hostnames are not exposed in the header:
```markdown
Conversation: refactor-auth-middleware
Saved: 2026-11-07 14:25

❯ Can you inspect the session token middleware and check why expired tokens return 500?
...
```

---

## Installation

Clone the repository and run the built-in installer to symlink both the CLI binary (`~/.local/bin/chat-save`) and the Claude Code skill (`~/.claude/skills/chat-save`):

```sh
git clone <remote-url> ~/tools/projects/chat-save
python3 ~/tools/projects/chat-save/bin/chat-save.py install
```

Once installed:
1. Run `/chat-save` directly **inside Claude Code** (automatically detects the active session UUID via a unique nonce).
2. Run `chat-save --session <uuid>` from **any terminal shell**.

To remove the symlinks at any time:
```sh
chat-save uninstall
```

---

## Usage & Automatic Folder Routing

### Inside Claude Code (`/chat-save`)

| Command Typed in Claude Code | Session Working Directory | Saved Destination Path |
| :--- | :--- | :--- |
| `/chat-save` | `~/work` | `~/Documents/work/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save` | `~/work/project/my-app` | `~/Documents/work/my-app/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save -n` | `~/work/project/my-app` | `~/Documents/work/my-app/conversations/<name>.md` |
| `/chat-save -a` | `~/work/project/my-app` | Same path, without `Directory` / `Session` / `Host` header lines |
| `/chat-save ~/Documents` | *Any* | `~/Documents/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save ~/Documents/archive` | *Any* | `~/Documents/archive/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |

> **Note on `notes-dir` Integration:** When run via `/chat-save` inside a repository whose `.claude/CLAUDE.md` defines `notes-dir: <path>` (such as `docs/notes`), the skill automatically routes the saved transcript to `<path>/conversations/`.

### From a Terminal Shell

```sh
chat-save --session <uuid> [--cwd <dir>] [--dry-run] [-n|--no-stamp] [-a|--anon] [dest]
```

---

## CLI Options & Actions

| Option / Action | Description |
| :--- | :--- |
| `--session <uuid>` | **Required for CLI run.** The Claude Code session UUID (matching `<uuid>.jsonl` under `~/.claude/projects/*/`). |
| `--cwd <dir>` | Working directory used to derive `<workspace>/<project>` when `[dest]` is omitted (defaults to `$PWD`; `Directory:` header uses the transcript's initial start folder). |
| `--dry-run` | Print the resolved destination file path (`[notice] dry run — would save <path>`) without writing anything. |
| `-n`, `--no-stamp` | Omit the `YYYY-MM-DD-HHMMSS-` date-time prefix from the filename (`<name>.md`). |
| `-a`, `--anon` | Omit `Directory:`, `Session:`, and `Host:` provenance lines from the Markdown header for external sharing. |
| `[dest]` | Optional base destination folder; transcripts are written to `<dest>/conversations/`. |
| `chat-save install` | Create `~/.local/bin/chat-save` and `~/.claude/skills/chat-save` symlinks. |
| `chat-save uninstall` | Remove both symlinks cleanly. |

---

## Security & Privacy Warning

> [!WARNING]
> **Saved Transcripts Contain Session Text**
> Even with `-a` / `--anon` (which removes header metadata), a saved conversation contains everything typed or pasted during the session. Always review the Markdown file for API keys, tokens, or private URLs before sharing or committing it to a public repository.

---

## Exit Codes & Project Layout

### Exit Codes
- `0` — Success (file saved, dry run printed, or symlink managed).
- `1` — Session transcript `.jsonl` not found or filesystem write error.
- `2` — Invalid command-line arguments or malformed session UUID.
- `130` — Interrupted by user (`Ctrl-C`).

### Directory Structure
```text
~/tools/projects/chat-save/
├── LICENSE
├── README.md
├── bin/chat-save.py           # Core CLI executable & JSONL-to-Markdown renderer
├── docs/
│   ├── PROJECT.md
│   └── STATUS.md
└── skills/chat-save/SKILL.md  # Claude Code /chat-save skill definition
```

---

## Frequently Asked Questions (FAQ)

**How is `chat-save` different from Claude Code's built-in `/export`?**  
Built-in `/export` requires specifying a filename manually each time. `/chat-save` automatically detects the active session UUID, names the file after your `/rename` title with a timestamp (`YYYY-MM-DD-HHMMSS-<slug>.md`), routes it to the right project notes folder, and prevents accidental overwrites with `-save-N.md` numbering.

**How does `chat-save` determine the `Directory:` header for `claude --resume`?**  
Claude Code only finds a session with `claude --resume` when run from the directory where the session **started**. `chat-save` reads the first `cwd` recorded in the `.jsonl` transcript so the `Directory:` header always shows the exact folder needed to resume that chat.

**Can I preview where a transcript will be saved without writing the file?**  
Yes. Pass `--dry-run` (for example, `chat-save --session <uuid> --dry-run`) to print the exact target file path without creating directories or writing to disk.
