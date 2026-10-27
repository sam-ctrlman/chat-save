# chat-save

Save a Claude Code conversation as readable text, with the folder and file name picked automatically.

Built-in `/export` only takes a file name. `/chat-save` knows where your notes live and what the conversation is called.

## Install

```sh
git clone <remote-url> ~/scripts/chat-save
python3 ~/scripts/chat-save/bin/chat-save.py install
```

After install, `chat-save` works in any shell and `/chat-save` works in Claude Code.

## Use

In Claude Code:

| Typed | Saved to |
|---|---|
| `/chat-save` (session in `~/work`) | `~/Documents/work/conversations/<name>.md` |
| `/chat-save` (session in `~/work/project/my-app`) | `~/Documents/work/my-app/conversations/<name>.md` |
| `/chat-save ~/Documents` | `~/Documents/conversations/<name>.md` |
| `/chat-save ~/Documents/work2` | `~/Documents/work2/conversations/<name>.md` |

- **Name:** the session name (`/rename`), else the automatic title, else the session uuid, made into a slug.
- **Never overwrites:** the 2nd save is `<name>-save-1.md`, the 3rd `<name>-save-2.md`, and so on.
- **Content:** your messages (`❯`), Claude's replies (`⏺`), one line per tool call. System reminders,
  skill bodies, tool output and subagent messages are left out.

From a shell:

```sh
chat-save --session <uuid> [--cwd <dir>] [--dry-run] [dest]
```

The slash command finds the uuid with the nonce method (echo a unique string, then grep the transcripts).

## Actions

| Action | What it does |
|--------|-------------|
| `chat-save --session <uuid> …` | Save the conversation (see above). `--dry-run` prints the target path only |
| `chat-save install` | Create bin + Claude command symlinks |
| `chat-save uninstall` | Remove both symlinks |

Exit codes: 0 ok, 1 transcript not found / write error, 2 usage.

⚠ A saved file holds everything said in the session, including anything pasted in. Keep it local.

## Layout

```
~/scripts/chat-save/
├── README.md
├── bin/chat-save.py
└── commands/chat-save.md
```
