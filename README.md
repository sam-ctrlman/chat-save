# chat-save

**CLI utility and multi-agent skill to export AI coding sessions (Claude Code, Google Antigravity, and extensible adapters) into clean, readable Markdown transcripts with automatic naming, project folder routing, provenance headers, and anonymous sharing (`--anon`).**

Built-in export commands often require manually typing a destination path and filename every time, and raw `.jsonl` session files in `~/.claude/projects/` or `~/.gemini/antigravity*/brain/` are cluttered with system reminders, internal metadata, and verbose tool payloads. `chat-save` automatically detects the agent and session title (`/rename`, AI title, or first prompt slug), routes the file into your project's notes directory, strips system noise, and saves a clean `.md` conversation log without ever overwriting previous saves.

---

## Why Use `chat-save`?

- **Multi-Agent Pluggable Adapters:** Automatically locates and renders transcripts from **Claude Code** (`~/.claude/projects/*/<uuid>.jsonl`) and **Google Antigravity** (`~/.gemini/antigravity*/brain/<uuid>/.system_generated/logs/transcript_full.jsonl`), with an extensible adapter registry ready for additional CLI agents (`codex`, `qwen-code`, `kimi`, `deepseek`, `glm`).
- **Automatic Title & Timestamp Naming:** Picks `--title`, the session name (`/rename`), automatic AI title, first prompt slug, or session UUID and saves as `<YYYY-MM-DD-HHMMSS>-<slug>.md` (or `<slug>.md` with `-n` / `--no-stamp`).
- **Smart Workspace & Project Routing:** Automatically derives the output folder from the folder your session started in (`~/Documents/<workspace>/<project>/conversations/` or your project's configured `notes-dir`).
- **Collision-Safe Saving:** Never overwrites an existing transcript — subsequent saves append `-save-1.md`, `-save-2.md`, and so on.
- **Readable Markdown Output:** Keeps user prompts (`❯`), assistant responses (`⏺`), and compact 1-line tool summaries (`⏺ Tool(...)`) while stripping `<system-reminder>` and `<ADDITIONAL_METADATA>` blocks, sidechains, compact summaries, and raw tool output blobs.
- **Anonymous Sharing Mode (`-a` / `--anon`):** Strips local provenance headers (`Agent:`, `Directory:`, `Session:`, `Host:`) when exporting a transcript to share externally.
- **Zero External Dependencies:** Pure Python 3 standard library.

---

## Example Saved Markdown Output

### Default Output (with Provenance Header)
```markdown
Conversation: refactor-auth-middleware
Saved: 2026-11-07 14:25
Agent: claude (sonnet-4-5)
Directory: /home/user/work/project/my-app
Session: 8f9a2c10-4b1e-4d3a-9c7e-123456789abc
Host: workstation-01

❯ Can you inspect the session token middleware and check why expired tokens return 500?

⏺ Read(/home/user/work/project/my-app/src/auth/middleware.ts)

⏺ The `verifyToken()` call throws `TokenExpiredError` before reaching the status handler. Let's catch it and return `401 Unauthorized`.
```

### Anonymous Mode (`chat-save -a`)
Omits `Agent:`, `Directory:`, `Session:`, and `Host:` so local filesystem paths and machine hostnames are not exposed in the header:
```markdown
Conversation: refactor-auth-middleware
Saved: 2026-11-07 14:25

❯ Can you inspect the session token middleware and check why expired tokens return 500?
...
```

---

## Installation

Clone the repository and run the built-in installer to symlink both the CLI binary (`~/.local/bin/chat-save`) and the skill (`~/.claude/skills/chat-save`):

```sh
git clone <remote-url> ~/tools/projects/chat-save
python3 ~/tools/projects/chat-save/bin/chat-save.py install
```

Once installed:
1. Run `/chat-save` directly **inside Claude Code or Antigravity**.
2. Run `chat-save --session <uuid>` from **any terminal shell**.

To remove the symlinks at any time:
```sh
chat-save uninstall
```

---

## Usage & Automatic Folder Routing

### Inside Claude Code or Antigravity (`/chat-save`)

| Command Typed | Session Start Folder | Saved Destination Path |
| :--- | :--- | :--- |
| `/chat-save` | `~/work` | `~/Documents/work/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save` | `~/work/project/my-app` | `~/Documents/work/my-app/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save -n` | `~/work/project/my-app` | `~/Documents/work/my-app/conversations/<name>.md` |
| `/chat-save` | `~/Documents/stepbooks` | `~/Documents/stepbooks/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` (no doubled `Documents/`) |
| `/chat-save -a` | `~/work/project/my-app` | Same path, without `Agent` / `Directory` / `Session` / `Host` header lines |
| `/chat-save ~/Documents` | *Any* | `~/Documents/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |
| `/chat-save ~/Documents/archive` | *Any* | `~/Documents/archive/conversations/<YYYY-MM-DD-HHMMSS>-<name>.md` |

> **Note on `notes-dir` Integration:** When run via `/chat-save` inside a repository whose `.claude/CLAUDE.md` or `.agents/rules/AGENTS.md` defines `notes-dir: <path>` (such as `docs/notes`), the skill automatically routes the saved transcript to `<path>/conversations/`.

### From a Terminal Shell

```sh
chat-save --session <uuid> [--agent <id>] [--title <text>] [--cwd <dir>] [--dry-run] [-n|--no-stamp] [-a|--anon] [dest]
```

---

## CLI Options & Actions

| Option / Action | Description |
| :--- | :--- |
| `--session <uuid>` | **Required for CLI run.** The session UUID (matching `<uuid>.jsonl` under `~/.claude/projects/*/` or `~/.gemini/antigravity*/brain/<uuid>/.system_generated/logs/`). |
| `--agent <id>` | Optional agent adapter name (`claude`, `antigravity`). Auto-detected from transcript location when omitted. |
| `--title <text>` | Optional title override slugified for the output filename and `Conversation:` header. |
| `--cwd <dir>` | Fallback folder used to derive `<workspace>/<project>` when the transcript records no start `cwd` (defaults to `$PWD`). |
| `--dry-run` | Print the resolved destination file path (`[notice] dry run — would save <path>`) without writing anything. |
| `-n`, `--no-stamp` | Omit the `YYYY-MM-DD-HHMMSS-` date-time prefix from the filename (`<name>.md`). |
| `-a`, `--anon` | Omit `Agent:`, `Directory:`, `Session:`, and `Host:` provenance lines from the Markdown header for external sharing. |
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
- `2` — Invalid command-line arguments, unknown adapter, or malformed session UUID.
- `130` — Interrupted by user (`Ctrl-C`).

### Directory Structure
```text
~/tools/projects/chat-save/
├── LICENSE
├── README.md
├── bin/chat-save.py           # Core CLI executable & multi-agent JSONL-to-Markdown renderer
├── docs/
│   ├── PROJECT.md
│   └── STATUS.md
├── skills/chat-save/SKILL.md  # Multi-agent /chat-save skill definition
└── tests/test_chat_save.py    # Unit test suite
```

---

## Frequently Asked Questions (FAQ)

**How is `chat-save` different from Claude Code's built-in `/export`?**  
Built-in `/export` requires specifying a filename manually each time and only works in Claude Code. `/chat-save` works across Claude Code and Antigravity, automatically detects the active session UUID, names the file with a timestamp (`YYYY-MM-DD-HHMMSS-<slug>.md`), routes it to the right project notes folder, and prevents accidental overwrites with `-save-N.md` numbering.

**How does `chat-save` determine the `Directory:` header?**  
For Claude Code, `claude --resume` only finds a session when run from the directory where the session **started**, so `chat-save` reads the first `cwd` recorded in the `.jsonl` transcript. For Antigravity, `chat-save` infers the workspace/project directory from `--cwd` or the earliest workspace path accessed in the transcript.

**Can I preview where a transcript will be saved without writing the file?**  
Yes. Pass `--dry-run` (for example, `chat-save --session <uuid> --dry-run`) to print the exact target file path without creating directories or writing to disk.
