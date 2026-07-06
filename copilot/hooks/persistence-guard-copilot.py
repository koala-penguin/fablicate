#!/usr/bin/env python3
"""Persistence guard for GitHub Copilot (VS Code agent hooks) — EXPERIMENTAL.

Blocks a premature stop when the model's last message ends with a plan/promise
instead of a completed result. Copilot's Stop hook has no documented
force-continue output, so this uses exit code 2 ("blocking error … show error
to model") to surface a keep-working message; behavior may vary by VS Code
version.

VS Code's transcript file format is NOT a stable hook API, so parsing is
best-effort across two shapes:
  1. Claude-style JSONL: {"type":"assistant","message":{"content":[...]}}
  2. Generic JSON lines: {"role":"assistant","content":"..."} (content may
     also be a list of {"type":"text","text":...} blocks)
Anything unrecognizable fails open (allow the stop). All errors fail open.

Safety rails:
  - Max 3 blocks per session (counter under ~/.copilot/fablicate-state/,
    pruned after 7 days).
  - Question endings ("?"), approval-wait phrases, and background-delegation
    promises always allow.
  - FABLICATE_OFF=1 disables entirely.
"""
import hashlib
import json
import os
import re
import sys
import time

STATE_DIR = os.path.expanduser("~/.copilot/fablicate-state")
MAX_BLOCKS_PER_SESSION = 3

PROMISE_RE = re.compile(
    r"(?i)("
    r"\bI(?:'ll| will) (?:now |start |begin |proceed |go ahead )"
    r"|\blet me (?:now )?(?:start|begin|proceed|go ahead)"
    r"|\babout to (?:start|begin|run)"
    r")"
)
WAITING_RE = re.compile(
    r"(?i)("
    r"if you (?:want|approve|say|prefer|confirm)"
    r"|when you(?:'re| are) ready"
    r"|awaiting (?:your )?(?:approval|confirmation|go-?ahead|input)"
    r"|for you to decide"
    r")"
)
WHITELIST_RE = re.compile(r"(?i)(let you know|background|running in the background)")


def read_stdin_json():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def counter_path(session_id):
    key = hashlib.sha1(session_id.encode()).hexdigest()[:16]
    return os.path.join(STATE_DIR, f"guard-{key}.count")


def read_counter(path):
    if not os.path.exists(path):
        return 0
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except Exception:
        return MAX_BLOCKS_PER_SESSION  # unreadable → fail toward allowing stop


def bump_counter(path):
    os.makedirs(STATE_DIR, exist_ok=True)
    count = read_counter(path) + 1
    with open(path, "w") as f:
        f.write(str(count))


def prune_state():
    try:
        cutoff = time.time() - 7 * 86400
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except Exception:
        pass


def text_of(content):
    """Extract plain text from a string or a list of text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def last_assistant_text(path):
    """Best-effort scan for the final assistant message text."""
    last = ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            # Shape 1: Claude-style JSONL
            if d.get("type") == "assistant" and isinstance(d.get("message"), dict):
                t = text_of(d["message"].get("content"))
                if t.strip():
                    last = t
            # Shape 2: generic role/content lines
            elif d.get("role") == "assistant":
                t = text_of(d.get("content"))
                if t.strip():
                    last = t
    return last


def main():
    # Kill switches: either env var, or an OFF file (GUI-launched VS Code
    # doesn't reliably inherit shell env vars).
    if os.environ.get("FABLICATE_OFF") == "1" or os.environ.get("CLAUDE_PERSIST") == "0":
        return 0
    if os.path.exists(os.path.join(STATE_DIR, "OFF")):
        return 0

    data = read_stdin_json()
    session_id = data.get("session_id") or ""
    transcript = data.get("transcript_path") or ""
    if not session_id or not transcript or not os.path.isfile(transcript):
        return 0

    prune_state()
    cpath = counter_path(session_id)
    if read_counter(cpath) >= MAX_BLOCKS_PER_SESSION:
        return 0

    tail = last_assistant_text(transcript).strip()
    if not tail:
        return 0

    last_line = ""
    for line in reversed(tail.splitlines()):
        if line.strip():
            last_line = line.strip()
            break

    ending = tail[-400:]
    if last_line.endswith("?") or WAITING_RE.search(ending) or WHITELIST_RE.search(ending):
        return 0

    if not (PROMISE_RE.search(last_line) or last_line.endswith(":")):
        return 0

    bump_counter(cpath)
    sys.stderr.write(
        "PERSISTENCE GUARD: do not stop yet. Your last message ends with a plan "
        "or promise instead of a completed result. Keep working: execute what "
        "you planned, retry after errors, and only end the turn when the task "
        "is complete or you are blocked on input only the user can provide. If "
        "everything IS complete, restate the final result plainly (no trailing "
        "plans or promises) and stop.\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: never trap the session
