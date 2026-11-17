#!/usr/bin/env python3
"""chat-save — save an AI coding conversation (Claude Code, Antigravity, etc.) as readable text, auto folder + auto name.

Usage:
  chat-save --session <uuid> [--agent <id>] [--title <text>] [--cwd <dir>] [--dry-run] [-n] [-a] [dest]
  chat-save install       # symlink into ~/.local/bin + ~/.claude/skills
  chat-save uninstall     # remove those symlinks
  chat-save --help

Folder:
  no dest  -> ~/Documents/<workspace>[/<project>]/conversations/  (from the chat start folder =
              first transcript cwd, --cwd only if none: ~/work -> work, ~/work/project/my-app ->
              work/my-app; "project"/"worktree" segments dropped; a start folder under ~/Documents
              is not doubled: ~/Documents/x -> ~/Documents/x/conversations/)
  dest     -> <dest>/conversations/
Name:
  --title if given, else the session name (/rename), else the auto title / first prompt slug,
  else the uuid -> <name>.md, then <name>-save-1.md, <name>-save-2.md, ... (never overwrites)

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
from typing import Callable


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def die(msg: str, code: int = 1):
    log("error", msg)
    sys.exit(code)


TOOL_NAME = Path(__file__).resolve().parent.parent.name
SYMLINK_TARGET = Path.home() / ".local" / "bin" / TOOL_NAME
CLAUDE_SKILL_TARGET = Path.home() / ".claude" / "skills" / TOOL_NAME
LEGACY_COMMAND_TARGET = Path.home() / ".claude" / "commands" / f"{TOOL_NAME}.md"

PROJECTS_DIR = Path.home() / ".claude" / "projects"
GEMINI_DIR = Path.home() / ".gemini"
DOCUMENTS = Path.home() / "Documents"
SKIP_SEGMENTS = {"project", "worktree"}
EXT = ".md"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

SYSTEM_TAGS = re.compile(r"<(system-reminder|local-command-caveat)>.*?</\1>", re.S)
COMMAND_RE = re.compile(r"<command-name>(.*?)</command-name>.*?(?:<command-args>(.*?)</command-args>)?", re.S)
USER_REQ_RE = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.S)
AGY_META_TAGS = re.compile(
    r"<(ADDITIONAL_METADATA|USER_SETTINGS_CHANGE|SYSTEM_MESSAGE|EPHEMERAL_MESSAGE)>.*?</\1>",
    re.S,
)


def _skill_source() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / TOOL_NAME


# ---------- shared formatting helpers ----------

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


def _folder(dest: str | None, cwd: Path) -> Path:
    if dest:
        return Path(dest).expanduser().resolve() / "conversations"
    try:
        rel = cwd.resolve().relative_to(Path.home())
    except ValueError:
        rel = Path()
    if rel.parts[:1] == ("Documents",):  # start folder already under ~/Documents: don't add it again
        rel = Path(*rel.parts[1:])
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


def _host() -> str:
    try:
        out = subprocess.run(["hostnamectl", "hostname"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return socket.gethostname()


# ---------- Claude Code adapter ----------

def _find_claude(session: str) -> Path | None:
    hits = sorted(PROJECTS_DIR.glob(f"*/{session}.jsonl"))
    return hits[0] if hits else None


def _title(entries: list[dict], session: str, title_override: str | None = None) -> str:
    if title_override and _slug(title_override):
        return _slug(title_override)
    # newest wins: a /rename after the auto title must take effect
    for kind, key in (("custom-title", "customTitle"), ("agent-name", "agentName"), ("ai-title", "aiTitle")):
        values = [e[key] for e in entries if e.get("type") == kind and e.get(key)]
        if values and _slug(values[-1]):
            return _slug(values[-1])
    if any(e.get("type") in ("USER_INPUT", "PLANNER_RESPONSE") for e in entries):
        return _title_antigravity(entries, session)
    return session


def _model_claude(entries: list[dict]) -> str | None:
    models = [
        (e.get("message") or {}).get("model") or e.get("model")
        for e in entries
        if (e.get("message") or {}).get("model") or e.get("model")
    ]
    if not models:
        return None
    m = str(models[-1])
    return m[7:] if m.startswith("claude-") else m


def _start_dir(entries: list[dict], fallback: Path) -> Path:
    # claude --resume only finds a chat from the folder it was STARTED in: first "cwd" of the transcript
    for e in entries:
        if e.get("cwd"):
            return Path(e["cwd"])
    if any(e.get("type") in ("USER_INPUT", "PLANNER_RESPONSE") for e in entries):
        return _start_dir_antigravity(entries, fallback)
    return fallback


def _tool_line(block: dict) -> str:
    inp = block.get("input") or {}
    detail = inp.get("description") or inp.get("file_path") or inp.get("skill") or inp.get("pattern") or ""
    return f"⏺ {block.get('name', 'tool')}({str(detail)[:100]})"


def _body_claude(entries: list[dict]) -> list[str]:
    out: list[str] = []
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
    return out


# ---------- Antigravity (agy) adapter ----------

def _find_antigravity(session: str) -> Path | None:
    for fname in ("transcript_full.jsonl", "transcript.jsonl"):
        hits = sorted(GEMINI_DIR.glob(f"antigravity*/brain/{session}/.system_generated/logs/{fname}"))
        if hits:
            return hits[0]
    return None


def _clean_agy_user(content: str) -> str:
    m = USER_REQ_RE.search(content)
    if m:
        return m.group(1).strip()
    return AGY_META_TAGS.sub("", content).strip()


def _title_antigravity(entries: list[dict], session: str, title_override: str | None = None) -> str:
    if title_override and _slug(title_override):
        return _slug(title_override)
    for e in entries:
        if e.get("type") == "USER_INPUT" and isinstance(e.get("content"), str):
            text = _clean_agy_user(e["content"])
            for line in text.splitlines():
                cleaned = re.sub(r"^[#>*\-\s]+", "", line).strip()
                if cleaned and _slug(cleaned):
                    return _slug(cleaned)[:60].strip("-")
    return session


def _model_antigravity(entries: list[dict]) -> str | None:
    models = [e.get("model") for e in entries if e.get("type") == "PLANNER_RESPONSE" and e.get("model")]
    return str(models[-1]) if models else None


def _start_dir_antigravity(entries: list[dict], fallback: Path) -> Path:
    home = Path.home()
    hidden_Top = {".claude", ".gemini", ".codex", ".antigravity", ".agents", ".config", ".local", ".ssh"}
    for e in entries[:40]:
        if e.get("type") != "PLANNER_RESPONSE":
            continue
        for tc in e.get("tool_calls") or []:
            args = tc.get("args") or {}
            for key in ("Path", "Cwd", "CommandLine"):
                val = str(args.get(key) or "").strip().strip('"').strip("'")
                for token in val.split():
                    token = token.strip("\"'`;,()")
                    if not token.startswith(str(home) + "/"):
                        continue
                    p = Path(token)
                    try:
                        rel = p.relative_to(home)
                    except ValueError:
                        continue
                    if not rel.parts or rel.parts[0] in hidden_Top:
                        continue
                    if len(rel.parts) >= 3 and rel.parts[1] in ("projects", "project"):
                        return home / rel.parts[0] / rel.parts[1] / rel.parts[2]
                    return home / rel.parts[0]
    return fallback


def _agy_tool_line(tc: dict) -> str:
    name = tc.get("name") or "tool"
    args = tc.get("args") or {}
    detail = (
        args.get("Path")
        or args.get("CommandLine")
        or args.get("toolSummary")
        or args.get("query")
        or args.get("Description")
        or ""
    )
    detail = str(detail).strip().strip('"')
    return f"⏺ {name}({detail[:100]})"


def _body_antigravity(entries: list[dict]) -> list[str]:
    out: list[str] = []
    for e in entries:
        etype = e.get("type")
        if etype == "USER_INPUT":
            text = _clean_agy_user(str(e.get("content") or ""))
            if text:
                out += ["", _block("❯", text)]
        elif etype == "PLANNER_RESPONSE":
            for tc in e.get("tool_calls") or []:
                out += ["", _agy_tool_line(tc)]
            text = str(e.get("content") or "").strip()
            if text:
                out += ["", _block("⏺", text)]
    return out


# ---------- Pluggable Multi-Agent Registry ----------
# Adding a new agent (codex, qwen-code, kimi, deepseek, glm, local-*) only requires registering
# its locator + extractor functions here.

AGENT_ALIASES = {
    "agy": "antigravity",
    "qwen": "qwen-code",
}

AGENT_ADAPTERS: dict[str, dict[str, Callable]] = {
    "claude": {
        "find": _find_claude,
        "title": _title,
        "model": _model_claude,
        "start_dir": _start_dir,
        "body": _body_claude,
    },
    "antigravity": {
        "find": _find_antigravity,
        "title": _title_antigravity,
        "model": _model_antigravity,
        "start_dir": _start_dir_antigravity,
        "body": _body_antigravity,
    },
    # Future standard slots (codex, qwen-code, kimi, deepseek, glm):
    # register find/title/model/start_dir/body once their local JSONL paths are enabled.
}

KNOWN_AGENTS = ("claude", "antigravity", "codex", "qwen-code", "kimi", "deepseek", "glm")


def _detect_agent(entries: list[dict], default: str = "claude") -> str:
    if any(e.get("type") in ("USER_INPUT", "PLANNER_RESPONSE") for e in entries):
        return "antigravity"
    return default


def _find_transcript(session: str, agent: str | None = None) -> tuple[Path, str]:
    if not UUID_RE.match(session):
        die(f"--session must be a uuid, got '{session}'", code=2)
    if agent:
        norm = AGENT_ALIASES.get(agent.lower(), agent.lower())
        if norm not in AGENT_ADAPTERS:
            die(
                f"transcript adapter for agent '{norm}' is not configured yet "
                f"(active adapters: {', '.join(AGENT_ADAPTERS)})",
                code=2,
            )
        hit = AGENT_ADAPTERS[norm]["find"](session)
        if not hit:
            die(f"no {norm} transcript found for session {session}")
        return hit, norm

    for name, adapter in AGENT_ADAPTERS.items():
        hit = adapter["find"](session)
        if hit:
            return hit, name

    die(
        f"no transcript for {session} under {PROJECTS_DIR} or "
        f"{GEMINI_DIR}/antigravity*/brain/{session}/.system_generated/logs/"
    )


def _render(
    entries: list[dict],
    title: str,
    session: str,
    cwd: Path,
    anon: bool = False,
    agent: str | None = None,
) -> str:
    # -a/--anon (rule ~/.claude/CLAUDE.md -> Note provenance): no Agent / Directory / Session / Host lines (D2=a)
    resolved_agent = AGENT_ALIASES.get((agent or "").lower(), (agent or "").lower()) or _detect_agent(entries)
    adapter = AGENT_ADAPTERS.get(resolved_agent, AGENT_ADAPTERS["claude"])
    model = adapter["model"](entries)
    agent_str = f"{resolved_agent} ({model})" if model else resolved_agent
    start_dir = adapter["start_dir"](entries, cwd)

    out = [
        f"Conversation: {title}",
        f"Saved: {datetime.now():%Y-%m-%d %H:%M}",
    ]
    if not anon:
        out += [
            f"Agent: {agent_str}",
            f"Directory: {start_dir}",
            f"Session: {session}",
            f"Host: {_host()}",
        ]
    out.append("")
    out += adapter["body"](entries)
    return "\n".join(out).rstrip() + "\n"


def cmd_run(
    session: str | None,
    cwd: str | None,
    dest: str | None,
    dry_run: bool,
    stamp: bool = True,
    anon: bool = False,
    agent: str | None = None,
    title_override: str | None = None,
) -> int:
    if not session:
        die("usage: chat-save --session <uuid> [--agent <id>] [--title <text>] [--cwd <dir>] [--dry-run] [dest]", code=2)
    transcript, resolved_agent = _find_transcript(session, agent)
    adapter = AGENT_ADAPTERS[resolved_agent]
    entries = _read_entries(transcript)
    cwd_path = Path(cwd).expanduser() if cwd else Path.cwd()
    title = adapter["title"](entries, session, title_override)
    start_dir = Path(cwd).expanduser() if (cwd and resolved_agent == "antigravity") else adapter["start_dir"](entries, cwd_path)
    folder = _folder(dest, start_dir)  # start folder wins; --cwd as override/fallback
    target = _free_name(folder, title, stamp)
    if dry_run:
        log("notice", f"dry run — would save {target}")
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(_render(entries, title, session, start_dir, anon, agent=resolved_agent))
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
    _install_claude_skill()
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


def _install_claude_skill() -> None:
    source = _skill_source()
    if not (source / "SKILL.md").exists():
        log("notice", f"skill source not found at {source / 'SKILL.md'} — skipping Claude integration")
        return
    _remove_legacy_command()
    target = CLAUDE_SKILL_TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == source:
        log("skip", f"skill symlink already correct: {target} -> {source}")
    else:
        if target.is_symlink():
            log("info", f"replacing existing skill symlink ({target} -> {target.resolve()})")
            target.unlink()
        elif target.exists():
            die(f"{target} exists and is not a symlink — refusing to overwrite")
        target.symlink_to(source)
        log("ok", f"skill symlink created: {target} -> {source}")
    _check_skill_ignored()


def _remove_legacy_command() -> None:
    # Before TOOL-SKILLDIR this tool linked ~/.claude/skills/<tool>.md; a leftover link would clash with the skill.
    legacy = LEGACY_COMMAND_TARGET
    if not legacy.is_symlink():
        if legacy.exists():
            log("notice", f"{legacy} is a real file, not this tool's link — left alone; remove it by hand if it duplicates the skill")
        return
    was = legacy.resolve()
    if _skill_source().parent.parent in was.parents:
        legacy.unlink()
        log("ok", f"removed old slash command symlink: {legacy} (was -> {was})")
    else:
        log("notice", f"{legacy} points outside this tool ({was}) — left alone")


def _check_skill_ignored() -> None:
    # Warn only, never edit ~/.claude/.gitignore (TOOL-SKILLDIR D3=a).
    claude_dir = CLAUDE_SKILL_TARGET.parent.parent
    rel = f"skills/{CLAUDE_SKILL_TARGET.name}"
    try:
        r = subprocess.run(["git", "-C", str(claude_dir), "check-ignore", "-q", rel], capture_output=True)
    except FileNotFoundError:
        return
    # 0 = ignored · 1 = not ignored · 128 = ~/.claude is not a git repo (fresh machine): stay quiet
    if r.returncode == 1:
        log("notice", f"{CLAUDE_SKILL_TARGET} is not git-ignored — add this line to {claude_dir}/.gitignore:  /{rel}")


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
    _uninstall_claude_skill()
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


def _uninstall_claude_skill() -> None:
    target = CLAUDE_SKILL_TARGET
    if not target.is_symlink() and not target.exists():
        log("info", f"no skill symlink at {target} to remove")
    elif not target.is_symlink():
        die(f"{target} exists but is not a symlink — refusing to remove")
    else:
        was = target.resolve()
        target.unlink()
        log("ok", f"removed skill symlink: {target} (was -> {was})")
    _remove_legacy_command()


# ---------- entry point ----------

def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in ("install", "uninstall"):
        return cmd_install() if sys.argv[1] == "install" else cmd_uninstall()
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(
            "Save a Claude Code or Antigravity conversation as text to "
            "<notes>/conversations/<YYYY-MM-DD-HHMMSS>-<name>[-save-N].md. "
            "Also: install, uninstall."
        ),
        epilog="exit codes: 0 ok, 1 transcript not found / write error, 2 usage",
    )
    parser.add_argument("--session", help="session uuid (the transcript file or brain folder name)")
    parser.add_argument("--agent", help="agent adapter (claude, antigravity; auto-detected when omitted)")
    parser.add_argument("--title", help="explicit title slug override when the transcript has no /rename entry")
    parser.add_argument("--cwd", help="fallback folder when the transcript has no cwd (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="print the target path, write nothing")
    parser.add_argument("-n", "--no-stamp", action="store_true", help="no YYYY-MM-DD-HHMMSS- prefix: <name>.md")
    parser.add_argument("-a", "--anon", action="store_true", help="leave out Agent / Directory / Session / Host (a file to share)")
    parser.add_argument("dest", nargs="?", help="base folder; the file goes to <dest>/conversations/")
    args = parser.parse_args()
    return cmd_run(
        args.session,
        args.cwd,
        args.dest,
        args.dry_run,
        stamp=not args.no_stamp,
        anon=args.anon,
        agent=args.agent,
        title_override=args.title,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("error", "interrupted")
        sys.exit(130)
