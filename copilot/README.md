# Fablicate for GitHub Copilot (VS Code)

Port of the three layers to VS Code agent mode (Copilot). Status per layer:

| Layer | Copilot equivalent | Status |
|---|---|---|
| Autonomy block | `.github/copilot-instructions.md` | ✅ direct port |
| /fablicate skill | custom agent (`.github/agents/fablicate.agent.md`) | ✅ direct port |
| Persistence guard | agent hook (`.github/hooks/`) `Stop` event | ⚠️ experimental |

## Install (per workspace)

```bash
# from the repo root of THIS project, into your target workspace:
cp copilot/copilot-instructions.md   <workspace>/.github/copilot-instructions.md
mkdir -p <workspace>/.github/agents <workspace>/.github/hooks
cp copilot/fablicate.agent.md        <workspace>/.github/agents/
cp copilot/hooks/fablicate-hooks.json        <workspace>/.github/hooks/
cp copilot/hooks/persistence-guard-copilot.py <workspace>/.github/hooks/
```

- The custom agent appears in the VS Code chat agent picker as **fablicate**.
- If you already have a `.github/copilot-instructions.md`, append the block instead of overwriting.

## Turning it off

- Env var: `FABLICATE_OFF=1` (or `CLAUDE_PERSIST=0`, same as the Claude version). Note GUI-launched VS Code may not inherit shell exports — on macOS use `launchctl setenv FABLICATE_OFF 1`, or use the file switch:
- File switch (always works): `touch ~/.copilot/fablicate-state/OFF` — remove the file to re-enable.
- Hard cap regardless: max **3 blocks per session** (unlike the Claude version's per-turn cap — after 3 the guard stays quiet for the rest of the session).

## Why the guard is experimental on Copilot

- VS Code's `Stop` hook has **no documented "block the stop and continue" output** (Claude Code's `decision: "block"`). The port uses the documented `exit code 2 = "blocking error … show error to model"` path, which surfaces the keep-working message to the model — behavior may vary across VS Code versions. If your build treats it as display-only, the guard degrades to a visible warning — harmless.
- VS Code documentation states the transcript file format is **not a stable hook API**. The adapter parses it best-effort (Claude-style JSONL and generic `role`/`content` JSON lines) and **fails open** — any parse failure allows the stop. The hook command itself is wrapped so a missing script also allows the stop.
- Hook `matcher`s are ignored by VS Code (all hooks run), and tool names differ — the adapter therefore relies only on the last assistant text, not tool/todo state.
- Promise/waiting phrase detection is **English-only** in this port (the Claude version also covers Korean).
- Windows: the hook command uses `sh`/`python3`; without them the hook emits a non-blocking warning and the guard is inert. WSL or adapting the command to PowerShell works.
- Alternative install: put the script at an **absolute path** under `~/.copilot/hooks` (user scope) and reference it absolutely — sidesteps any working-directory ambiguity.

## Note if you also use Claude Code

VS Code reads hooks from `~/.claude/settings.json` and `.claude/settings.json` for compatibility. If you installed the Claude Code version of fablicate, the original `persistence-guard.py` may already fire inside VS Code — but it parses Claude transcripts, so on Copilot transcripts it will simply fail open (allow every stop). Install this port for actual guard behavior in Copilot, and expect both to run side by side harmlessly.
