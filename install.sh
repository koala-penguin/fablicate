#!/usr/bin/env bash
# Fablicate manual installer (alternative to the plugin route — see README).
# Idempotent: safe to re-run. Requires python3.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing fablicate into $CLAUDE_DIR"

# 1. Hook script
mkdir -p "$CLAUDE_DIR/hooks"
cp "$REPO_DIR/hooks/persistence-guard.py" "$CLAUDE_DIR/hooks/persistence-guard.py"
echo "  [ok] hooks/persistence-guard.py"

# 2. Skill
mkdir -p "$CLAUDE_DIR/skills"
cp -r "$REPO_DIR/skills/fablicate" "$CLAUDE_DIR/skills/"
echo "  [ok] skills/fablicate"

# 3. Merge Stop hook into settings.json (append once, never clobber)
python3 - "$CLAUDE_DIR/settings.json" <<'PYEOF'
import json, os, sys

path = sys.argv[1]
settings = {}
if os.path.exists(path):
    with open(path) as f:
        settings = json.load(f)

entry = {
    "hooks": [
        {
            "type": "command",
            "command": "python3 $HOME/.claude/hooks/persistence-guard.py",
            "timeout": 15,
            "statusMessage": "Persistence guard: checking for unfinished work...",
        }
    ]
}

stop = settings.setdefault("hooks", {}).setdefault("Stop", [])
already = any(
    "persistence-guard.py" in h.get("command", "")
    for grp in stop
    for h in grp.get("hooks", [])
)
if already:
    print("  [ok] settings.json Stop hook already present")
else:
    stop.append(entry)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  [ok] settings.json Stop hook appended")
PYEOF

# 4. Autonomy block into CLAUDE.md (append once)
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
MARKER="## Autonomy & persistence"
if [ -f "$CLAUDE_MD" ] && grep -q "$MARKER" "$CLAUDE_MD"; then
  echo "  [ok] CLAUDE.md autonomy block already present"
else
  # extract the fenced block from docs/autonomy-block.md
  awk '/^```markdown$/{flag=1;next}/^```$/{flag=0}flag' "$REPO_DIR/docs/autonomy-block.md" >> "$CLAUDE_MD"
  echo "  [ok] CLAUDE.md autonomy block appended"
fi

echo "==> Done. Takes effect on your next Claude Code session."
echo "    Invoke marathon mode with: /fablicate <task>   (off: 'fablicate off')"
echo "    Opt out per-process with:  CLAUDE_PERSIST=0"
