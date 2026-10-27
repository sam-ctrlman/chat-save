# chat-save

TODO: one-line description of what chat-save automates.

## Install

```sh
git clone <remote-url> ~/scripts/chat-save
python3 ~/scripts/chat-save/bin/chat-save.py install
```

After install, `chat-save` works in any shell and `/chat-save` works in Claude Code.

## Actions

| Action | What it does |
|--------|-------------|
| `chat-save` / `chat-save run` | TODO: the automated workflow |
| `chat-save install` | Create bin + Claude command symlinks |
| `chat-save uninstall` | Remove both symlinks |

## Layout

```
~/scripts/chat-save/
├── README.md
├── bin/chat-save.py
└── commands/chat-save.md
```

## Next steps after scaffolding

1. Edit `bin/chat-save.py` — replace the `cmd_run()` body with the deterministic
   steps this tool should automate. Keep each step idempotent (start with a
   `[skip]` fast-path when the work is already done).
2. Update this README and the `description:` in `commands/chat-save.md`.
3. `git add -A && git commit` the changes.
4. (Optional) add a remote and `git push -u origin main`.
