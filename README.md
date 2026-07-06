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

### 1. Autonomy block
Copy the block from [docs/autonomy-block.md](docs/autonomy-block.md) to the top of `~/.claude/CLAUDE.md`.

### 2. Persistence guard hook
```bash
cp hooks/persistence-guard.py ~/.claude/hooks/
```
Then merge the entry from [settings/stop-hook.json](settings/stop-hook.json) into the `hooks.Stop` array of `~/.claude/settings.json` (append — don't replace your existing Stop hooks). Takes effect on the next session.

### 3. Skill
```bash
cp -r skills/fablicate ~/.claude/skills/
```
Invoke with `/fablicate <task>`. Turn off with `fablicate off`.

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

## Caveats

- The two env/cwd opt-out gates reflect the author's setup — adjust them to whatever your own headless jobs set.
- The skill references `superpowers:verification-before-completion` (from the [Superpowers](https://github.com/obra/superpowers) plugin) — optional; the contract stands without it.
- Heuristics are tuned for English + Korean promise phrasing; extend `PROMISE_RE` / `WAITING_RE` for other languages.

## License

MIT
