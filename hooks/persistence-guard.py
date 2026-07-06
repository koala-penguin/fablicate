#!/usr/bin/env python3
"""Persistence guard — Fable-5-style "keep working" Stop hook.

Blocks a premature stop when the CURRENT TURN shows unfinished work:
  1. Objective: the latest TodoWrite in this turn still has pending or
     in_progress items.
  2. Heuristic: the last assistant text ENDS with a plan/promise to act
     ("I'll now...", "진행할게요", a trailing ":" with no tool call after)
     instead of a result.

Turn-scoped: only entries after the last real user message are considered,
so abandoned tasks from earlier in a long-lived session are never resurrected.

Safety rails (all fail-open — any error allows the stop):
  - Honors stop_hook_active: at most 2 hook-driven continuations, hard cap 3
    blocks per user turn (counter keyed to session+turn, so each new user
    prompt resets the budget).
  - Waiting-on-user endings always allow: "?", conditional approval forms
    ("요청하시면", "if you approve", "awaiting your go-ahead").
  - Background-delegation promises allow ("let you know", "알려드릴게요",
    "background", "run_in_background") — ending the turn while a background
    job runs is a valid completion.
  - Headless digest children (AGENTMEMORY_SDK_CHILD=1), job cwds under
    ~/jobs/, and CLAUDE_PERSIST=0 are exempt.
  - Synthetic API-error entries (model "<synthetic>") are ignored.

Blocking output: {"decision": "block", "reason": "..."} on stdout, exit 0.
Allowing: plain exit 0.
"""
import hashlib
import json
import os
import re
import sys
import time

STATE_DIR = os.path.expanduser("~/.claude/hooks/state")
MAX_BLOCKS_PER_TURN = 3
MAX_CHAIN_CONTINUATIONS = 2  # blocks allowed while stop_hook_active is true

# Planning/promise phrases that mean the turn ended before the work did.
# Applied to the LAST non-empty line only.
PROMISE_RE = re.compile(
    r"(?i)("
    r"\bI(?:'ll| will) (?:now |start |begin |proceed |go ahead )"
    r"|\blet me (?:now )?(?:start|begin|proceed|go ahead)"
    r"|\babout to (?:start|begin|run)"
    r"|진행하겠|시작하겠|진행할게|시작할게"
    r")"
)
# Endings that mean we are legitimately waiting on the user.
WAITING_RE = re.compile(
    r"(?i)("
    r"요청하시면|원하시면|승인하시면|말씀하시면|시작이라고 하시면"
    r"|if you (?:want|approve|say|prefer|confirm)"
    r"|when you(?:'re| are) ready"
    r"|awaiting (?:your )?(?:approval|confirmation|go-?ahead|input)"
    r"|for you to decide"
    r")"
)
# Completion-style promises that legitimately end a turn (background work).
WHITELIST_RE = re.compile(
    r"(?i)(let you know|알려드릴|알려 드릴|완료되면|끝나면|background|백그라운드|run_in_background)"
)


def read_stdin_json():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def counter_path(session_id, turn_id):
    key = hashlib.sha1(f"{session_id}:{turn_id}".encode()).hexdigest()[:16]
    return os.path.join(STATE_DIR, f"persist-{key}.count")


def read_counter(path):
    """Fail-open toward ALLOWING the stop: unreadable counter counts as maxed."""
    if not os.path.exists(path):
        return 0
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except Exception:
        return MAX_BLOCKS_PER_TURN


def bump_counter(path):
    os.makedirs(STATE_DIR, exist_ok=True)
    count = read_counter(path) + 1
    with open(path, "w") as f:
        f.write(str(count))


def prune_state():
    """Drop counter files older than 7 days so STATE_DIR stays small."""
    try:
        cutoff = time.time() - 7 * 86400
        for name in os.listdir(STATE_DIR):
            p = os.path.join(STATE_DIR, name)
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except Exception:
        pass


def is_real_user_message(d):
    """A genuine user prompt (turn boundary) — not a tool_result carrier."""
    if d.get("type") != "user" or d.get("isSidechain") or d.get("isMeta"):
        return False
    content = (d.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(b.get("type") == "text" for b in content if isinstance(b, dict))
    return False


def scan_transcript(path):
    """Return (incomplete_todos, last_text, tool_use_after_text, turn_id)
    for the CURRENT turn only (after the last real user message)."""
    todos = []
    last_text = ""
    tool_after_text = False
    turn_id = "no-user-msg"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("isSidechain"):
                continue
            if is_real_user_message(d):
                # New turn: reset everything scoped to the previous turn.
                turn_id = d.get("uuid") or turn_id
                todos = []
                last_text = ""
                tool_after_text = False
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            if msg.get("model") == "<synthetic>":
                continue  # API-error placeholder, not model output
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            texts = []
            saw_tool_after = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    texts.append(block.get("text", ""))
                    saw_tool_after = False
                elif btype == "tool_use":
                    if texts:
                        saw_tool_after = True
                    inp = block.get("input") or {}
                    if block.get("name") == "TodoWrite" and isinstance(inp.get("todos"), list):
                        todos = inp["todos"]
            if texts:
                last_text = "\n".join(texts)
                tool_after_text = saw_tool_after

    incomplete = [
        (t.get("content") or t.get("subject") or "todo")
        for t in todos
        if isinstance(t, dict) and t.get("status") in ("pending", "in_progress")
    ]
    return incomplete, last_text, tool_after_text, turn_id


def main():
    data = read_stdin_json()

    # Gates: headless digest children, job cwds, explicit opt-out.
    if os.environ.get("AGENTMEMORY_SDK_CHILD") == "1":
        return
    if os.environ.get("CLAUDE_PERSIST") == "0":
        return
    cwd = data.get("cwd") or ""
    if cwd.startswith(os.path.expanduser("~/jobs")):
        return

    session_id = data.get("session_id") or ""
    transcript = data.get("transcript_path") or ""
    if not session_id or not transcript or not os.path.isfile(transcript):
        return

    prune_state()

    incomplete, last_text, tool_after_text, turn_id = scan_transcript(transcript)
    tail = last_text.strip()
    if not tail:
        return

    cpath = counter_path(session_id, turn_id)
    count = read_counter(cpath)
    if count >= MAX_BLOCKS_PER_TURN:
        return
    if data.get("stop_hook_active") and count >= MAX_CHAIN_CONTINUATIONS:
        return

    last_line = ""
    for line in reversed(tail.splitlines()):
        if line.strip():
            last_line = line.strip()
            break

    ending = tail[-400:]
    if last_line.endswith("?"):
        return  # genuinely waiting on the user
    if WAITING_RE.search(ending):
        return  # waiting on user approval/decision
    if WHITELIST_RE.search(ending):
        return  # background delegation is a valid completion

    reasons = []
    if incomplete:
        reasons.append("Unfinished todos this turn: " + "; ".join(str(x) for x in incomplete[:5]))
    if PROMISE_RE.search(last_line):
        reasons.append("Your last line is a plan or promise instead of a completed result.")
    elif last_line.endswith(":") and not tool_after_text:
        reasons.append("Your last line ends with ':' — the content it promises never arrived.")

    if not reasons:
        return

    bump_counter(cpath)
    print(json.dumps({
        "decision": "block",
        "reason": (
            "PERSISTENCE GUARD: do not stop yet. "
            + " ".join(reasons)
            + " Keep working: execute what you planned, retry after errors, and only "
            "end the turn when the task is complete or you are blocked on input only "
            "the user can provide. If everything IS complete, restate the final result "
            "plainly (no trailing plans or promises) and stop."
        ),
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail-open: never trap the session
    sys.exit(0)
