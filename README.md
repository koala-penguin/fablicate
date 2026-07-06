# Fablicate

Give any Claude Code model **Fable-5-style persistence**: long, focused, autonomous stretches of work — instead of doing a little, stopping, and asking "Shall I continue?".

Born from a simple observation: newer frontier models keep working until the task is actually done, while older ones hand work back every few steps. Most of that gap turns out to be reproducible with prompt rules + harness hooks.

## The three layers

| Layer | What it is | When it acts |
|---|---|---|
| **Autonomy block** ([docs/autonomy-block.md](docs/autonomy-block.md)) | Always-on rules in your global `CLAUDE.md` | Every turn, every session |
| **Persistence guard** ([hooks/persistence-guard.py](hooks/persistence-guard.py)) | A `Stop` hook that mechanically blocks premature stops | When the model tries to stop with unfinished work |
| **/fablicate skill** ([skills/fablicate/SKILL.md](skills/fablicate/SKILL.md)) | On-demand "marathon mode" contract for a single task | When you invoke `/fablicate <task>` |

Layer 1 sets the default behavior, layer 2 is the mechanical backstop when the model ignores it, layer 3 is the intensified opt-in mode.

## Install

### Option A — as a Claude Code plugin (recommended, 2 commands)

Inside Claude Code:
```
/plugin marketplace add koala-penguin/fablicate
/plugin install fablicate@fablicate
```
This registers the Stop hook and the skill automatically (skill becomes `/fablicate:fablicate`). Then paste the [autonomy block](docs/autonomy-block.md) into `~/.claude/CLAUDE.md` — plugins can't ship always-on instructions, so that one step stays manual.

### Option B — manual install script

```bash
git clone https://github.com/koala-penguin/fablicate.git
cd fablicate && ./install.sh
```
Idempotent: copies the hook + skill, appends the Stop-hook entry to `~/.claude/settings.json` (never clobbers existing hooks), and appends the autonomy block to `~/.claude/CLAUDE.md` if missing. Takes effect on the next session.

### For AI agents installing this

If you are a coding agent setting this up for your user, prefer Option B non-interactively:
1. `git clone https://github.com/koala-penguin/fablicate.git /tmp/fablicate && /tmp/fablicate/install.sh`
2. Verify: `jq '.hooks.Stop' ~/.claude/settings.json` (or `python3 -c "import json;print(json.load(open('$HOME/.claude/settings.json'))['hooks']['Stop'])"`) shows a `persistence-guard.py` entry; `~/.claude/skills/fablicate/SKILL.md` exists; `~/.claude/CLAUDE.md` contains "Autonomy & persistence".
3. Tell your user it takes effect on the next session, and that `CLAUDE_PERSIST=0` disables the guard for any headless/scheduled jobs they run — check whether they have such jobs and gate them.

Invoke marathon mode with `/fablicate <task>`. Turn off with `fablicate off`.

## How the guard decides

Scans the session transcript — **current turn only** (everything after your last message):

**Blocks the stop when**
- the latest `TodoWrite` still has `pending` / `in_progress` items, or
- the model's last line is a plan/promise ("I'll now…", "진행할게요") or a dangling `:` with no tool call after it.

**Always allows the stop when**
- the last line ends with `?` or an approval-wait phrase ("if you approve", "요청하시면") — genuinely waiting on you,
- the ending mentions background delegation ("let you know", "run_in_background") — launching a background job is a valid completion,
- the block budget is spent: **max 3 blocks per user turn** (resets on your next prompt), max 2 while `stop_hook_active`,
- anything errors — the guard is fail-open everywhere; it can never trap a session.

**Opt-outs:** `CLAUDE_PERSIST=0` env var, working dirs under `~/jobs/` (headless scheduled jobs), `AGENTMEMORY_SDK_CHILD=1` (example of gating your own headless children — adapt to your setup).

Performance: full scan of a 24.5 MB transcript ≈ 0.1 s.

## GitHub Copilot (VS Code) port

All three layers have Copilot equivalents — instructions file, custom agent, and an experimental Stop-hook guard adapter. See [copilot/README.md](copilot/README.md).

## Caveats

- The two env/cwd opt-out gates reflect the author's setup — adjust them to whatever your own headless jobs set.
- The skill references `superpowers:verification-before-completion` (from the [Superpowers](https://github.com/obra/superpowers) plugin) — optional; the contract stands without it.
- Heuristics are tuned for English + Korean promise phrasing; extend `PROMISE_RE` / `WAITING_RE` for other languages.

## License

MIT
