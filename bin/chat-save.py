#!/usr/bin/env python3
"""chat-save — save a Claude Code conversation as readable text, auto folder + auto name.

Usage:
  chat-save --session <uuid> [--cwd <dir>] [--dry-run] [-n] [-a] [dest]
  chat-save install       # symlink into ~/.local/bin + ~/.claude/commands
  chat-save uninstall     # remove those symlinks
  chat-save --help

Folder:
  no dest  -> ~/Documents/<workspace>[/<project>]/conversations/  (from --cwd: ~/work -> work,
              ~/work/project/my-app -> work/my-app; "project"/"worktree" segments dropped)
  dest     -> <dest>/conversations/
Name:
  the session name (/rename), else the auto title, else the uuid -> <name>.md,
  then <name>-save-1.md, <name>-save-2.md, ... (never overwrites)

Exit codes: 0 ok, 1 transcript not found / write error, 2 usage.

Scaffolded by `forge`. The tool name is derived from the repo directory, so
nothing here is hardcoded — rename the repo and it follows.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def die(msg: str, code: int = 1):
    log("error", msg)
    sys.exit(code)


TOOL_NAME = Path(__file__).resolve().parent.parent.name
SYMLINK_TARGET = Path.home() / ".local" / "bin" / TOOL_NAME
CLAUDE_COMMAND_TARGET = Path.home() / ".claude" / "commands" / f"{TOOL_NAME}.md"

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DOCUMENTS = Path.home() / "Documents"
SKIP_SEGMENTS = {"project", "worktree"}
EXT = ".md"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _command_source() -> Path:
    return Path(__file__).resolve().parent.parent / "commands" / f"{TOOL_NAME}.md"


# ---------- the workflow ----------

def _find_transcript(session: str) -> Path:
    if not UUID_RE.match(session):
        die(f"--session must be a uuid, got '{session}'", code=2)
    hits = sorted(PROJECTS_DIR.glob(f"*/{session}.jsonl"))
    if not hits:
        die(f"no transcript {session}.jsonl under {PROJECTS_DIR}")
    return hits[0]


def _read_entries(path: Path) -> list[dict]:
    entries = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _title(entries: list[dict], session: str) -> str:
    # newest wins: a /rename after the auto title must take effect
    for kind, key in (("custom-title", "customTitle"), ("agent-name", "agentName"), ("ai-title", "aiTitle")):
        values = [e[key] for e in entries if e.get("type") == kind and e.get(key)]
        if values and _slug(values[-1]):
            return _slug(values[-1])
    return session


def _folder(dest: str | None, cwd: Path) -> Path:
    if dest:
        return Path(dest).expanduser().resolve() / "conversations"
    try:
        rel = cwd.resolve().relative_to(Path.home())
    except ValueError:
        rel = Path()
    parts = [p for p in rel.parts if p not in SKIP_SEGMENTS][:2]
    return DOCUMENTS.joinpath(*parts, "conversations")


def _free_name(folder: Path, name: str, stamp: bool = True) -> Path:
    # default name: YYYY-MM-DD-HHMMSS-<name> (global "Note filenames" rule); --no-stamp -> <name>
    if stamp:
        name = f"{datetime.now():%Y-%m-%d-%H%M%S}-{name}"
    target = folder / f"{name}{EXT}"
    n = 0
    while target.exists():
        n += 1
        target = folder / f"{name}-save-{n}{EXT}"
    return target


SYSTEM_TAGS = re.compile(r"<(system-reminder|local-command-caveat)>.*?</\1>", re.S)
COMMAND_RE = re.compile(r"<command-name>(.*?)</command-name>.*?(?:<command-args>(.*?)</command-args>)?", re.S)


def _clean(text: str) -> str:
    text = SYSTEM_TAGS.sub("", text)
    m = COMMAND_RE.search(text)
    if m:
        text = f"{m.group(1)} {m.group(2) or ''}".strip()
    text = re.sub(r"</?(command-message|local-command-stdout)>", "", text)
    return text.strip()


def _block(marker: str, text: str) -> str:
    lines = text.splitlines() or [""]
    return "\n".join([f"{marker} {lines[0]}"] + [f"  {ln}" if ln else "" for ln in lines[1:]])


def _tool_line(block: dict) -> str:
    inp = block.get("input") or {}
    detail = inp.get("description") or inp.get("file_path") or inp.get("skill") or inp.get("pattern") or ""
    return f"⏺ {block.get('name', 'tool')}({str(detail)[:100]})"


def _start_dir(entries: list[dict], fallback: Path) -> Path:
    # claude --resume only finds a chat from the folder it was STARTED in: first "cwd" of the transcript
    for e in entries:
        if e.get("cwd"):
            return Path(e["cwd"])
    return fallback


def _host() -> str:
    try:
        out = subprocess.run(["hostnamectl", "hostname"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return socket.gethostname()


def _render(entries: list[dict], title: str, session: str, cwd: Path, anon: bool = False) -> str:
    # -a/--anon (rule ~/.claude/CLAUDE.md -> Note provenance): no Directory / Session / Host lines
    out = [
        f"Conversation: {title}",
        f"Saved: {datetime.now():%Y-%m-%d %H:%M}",
    ]
    if not anon:
        out += [f"Directory: {_start_dir(entries, cwd)}", f"Session: {session}", f"Host: {_host()}"]
    out.append("")
    for e in entries:
        if e.get("type") not in ("user", "assistant"):
            continue
        if e.get("isSidechain") or e.get("isMeta") or e.get("isCompactSummary"):
            continue
        content = (e.get("message") or {}).get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
        for b in blocks:
            if b.get("type") == "text":
                text = _clean(b.get("text", ""))
                if text:
                    out += ["", _block("❯" if e["type"] == "user" else "⏺", text)]
            elif b.get("type") == "tool_use":
                out += ["", _tool_line(b)]
    return "\n".join(out).rstrip() + "\n"


def cmd_run(session: str | None, cwd: str | None, dest: str | None, dry_run: bool, stamp: bool = True,
            anon: bool = False) -> int:
    if not session:
        die("usage: chat-save --session <uuid> [--cwd <dir>] [--dry-run] [dest]", code=2)
    transcript = _find_transcript(session)
    entries = _read_entries(transcript)
    cwd_path = Path(cwd).expanduser() if cwd else Path.cwd()
    title = _title(entries, session)
    folder = _folder(dest, cwd_path)
    target = _free_name(folder, title, stamp)
    if dry_run:
        log("notice", f"dry run — would save {target}")
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(_render(entries, title, session, cwd_path, anon))
    except OSError as exc:
        die(f"cannot write {target}: {exc}")
    log("ok", f"saved {target}")
    return 0


# ---------- install / uninstall ----------

def cmd_install() -> int:
    script_path = Path(__file__).resolve()
    mode = script_path.stat().st_mode
    if not (mode & 0o111):
        script_path.chmod(mode | 0o755)
        log("ok", f"made script executable: {script_path}")
    else:
        log("skip", f"script already executable: {script_path}")
    _install_bin_symlink(script_path)
    _install_claude_command()
    return _install_check_path()


def _install_bin_symlink(script_path: Path) -> None:
    SYMLINK_TARGET.parent.mkdir(parents=True, exist_ok=True)
    if SYMLINK_TARGET.is_symlink():
        current = SYMLINK_TARGET.resolve()
        if current == script_path:
            log("skip", f"bin symlink already correct: {SYMLINK_TARGET} -> {script_path}")
            return
        log("info", f"replacing existing bin symlink ({SYMLINK_TARGET} -> {current})")
        SYMLINK_TARGET.unlink()
    elif SYMLINK_TARGET.exists():
        die(f"{SYMLINK_TARGET} exists and is not a symlink — refusing to overwrite")
    SYMLINK_TARGET.symlink_to(script_path)
    log("ok", f"bin symlink created: {SYMLINK_TARGET} -> {script_path}")


def _install_claude_command() -> None:
    source = _command_source()
    if not source.exists():
        log("notice", f"slash command source not found at {source} — skipping Claude integration")
        return
    CLAUDE_COMMAND_TARGET.parent.mkdir(parents=True, exist_ok=True)
    if CLAUDE_COMMAND_TARGET.is_symlink():
        current = CLAUDE_COMMAND_TARGET.resolve()
        if current == source:
            log("skip", f"slash command symlink already correct: {CLAUDE_COMMAND_TARGET} -> {source}")
            return
        log("info", f"replacing existing slash command symlink ({CLAUDE_COMMAND_TARGET} -> {current})")
        CLAUDE_COMMAND_TARGET.unlink()
    elif CLAUDE_COMMAND_TARGET.exists():
        die(f"{CLAUDE_COMMAND_TARGET} exists and is not a symlink — refusing to overwrite")
    CLAUDE_COMMAND_TARGET.symlink_to(source)
    log("ok", f"slash command symlink created: {CLAUDE_COMMAND_TARGET} -> {source}")


def _install_check_path() -> int:
    on_path = shutil.which(TOOL_NAME)
    if on_path:
        log("ok", f"{TOOL_NAME} on PATH: {on_path}")
        return 0
    log("notice", f"{SYMLINK_TARGET.parent} is not on PATH — add this to your shell rc:")
    log("notice", f'  export PATH="{SYMLINK_TARGET.parent}:$PATH"')
    return 0


def cmd_uninstall() -> int:
    script_path = Path(__file__).resolve()
    _uninstall_bin_symlink()
    _uninstall_claude_command()
    log("info", f"to reinstall: python3 {script_path} install")
    return 0


def _uninstall_bin_symlink() -> None:
    if not SYMLINK_TARGET.is_symlink() and not SYMLINK_TARGET.exists():
        log("info", f"no bin symlink at {SYMLINK_TARGET} to remove")
        return
    if not SYMLINK_TARGET.is_symlink():
        die(f"{SYMLINK_TARGET} exists but is not a symlink — refusing to remove")
    target = SYMLINK_TARGET.resolve()
    SYMLINK_TARGET.unlink()
    log("ok", f"removed bin symlink: {SYMLINK_TARGET} (was -> {target})")


def _uninstall_claude_command() -> None:
    if not CLAUDE_COMMAND_TARGET.is_symlink() and not CLAUDE_COMMAND_TARGET.exists():
        log("info", f"no slash command symlink at {CLAUDE_COMMAND_TARGET} to remove")
        return
    if not CLAUDE_COMMAND_TARGET.is_symlink():
        die(f"{CLAUDE_COMMAND_TARGET} exists but is not a symlink — refusing to remove")
    target = CLAUDE_COMMAND_TARGET.resolve()
    CLAUDE_COMMAND_TARGET.unlink()
    log("ok", f"removed slash command symlink: {CLAUDE_COMMAND_TARGET} (was -> {target})")


# ---------- entry point ----------

def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in ("install", "uninstall"):
        return cmd_install() if sys.argv[1] == "install" else cmd_uninstall()
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(
            "Save a Claude Code conversation as text to <notes>/conversations/<YYYY-MM-DD-HHMMSS>-<name>[-save-N].md. "
            "Also: install, uninstall."
        ),
        epilog="exit codes: 0 ok, 1 transcript not found / write error, 2 usage",
    )
    parser.add_argument("--session", help="session uuid (the transcript file name)")
    parser.add_argument("--cwd", help="directory the session runs in (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="print the target path, write nothing")
    parser.add_argument("-n", "--no-stamp", action="store_true", help="no YYYY-MM-DD-HHMMSS- prefix: <name>.md")
    parser.add_argument("-a", "--anon", action="store_true", help="leave out Directory / Session / Host (a file to share)")
    parser.add_argument("dest", nargs="?", help="base folder; the file goes to <dest>/conversations/")
    args = parser.parse_args()
    return cmd_run(args.session, args.cwd, args.dest, args.dry_run, stamp=not args.no_stamp, anon=args.anon)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("error", "interrupted")
        sys.exit(130)
