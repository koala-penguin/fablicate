---
name: fablicate
description: Marathon mode — one long uninterrupted autonomous run of a task. Front-load every question, then execute to full completion without handing work back.
---

# Fablicate — single-turn marathon mode

Run the given task in one long, focused, autonomous stretch. Violating the letter of this contract is violating its spirit.

## The contract

1. **Front-load questions — once, then never.** Before starting, scan the task for genuine user-only decisions (destructive actions, spending real money, publishing externally, true scope forks). Ask ALL of them in ONE batched message. If there are none — say nothing, start. After this point, zero questions until done: every remaining ambiguity is resolved by your own judgment, stated in the final report, not asked.
2. **Execute to completion in this turn.** Plan silently, then do the work: all steps, all retries, all fallbacks. Tool failed → try another tool. Error → diagnose and retry. Information missing → find it yourself (search, read, measure).
3. **Verify before claiming done.** Run the thing, run the tests, check the output file exists and is sane — evidence, not assertion.
4. **End with a result, not a plan.** The final message states what was built/changed/found, what was verified, and any judgment calls made. It must not end with a question, a next-steps list you could have executed, or a promise ("I'll…").
5. **Still allowed to end the turn:** a launched background task with completion notification, and hard blocks that only the user can clear (permission denied, credentials, paid action awaiting approval) — state the block plainly and stop.

## Red flags — you are about to break the contract

- "Let me check with the user before the next phase" (phase = not a user-only decision)
- "This is a good stopping point" (there is no good stopping point before done)
- "I'll ask because the spec is vague" mid-task (judgment call — make it, log it)
- Final paragraph starts with "Next steps" or "Shall I…"
- "The context is getting long" (irrelevant — keep going)

| Rationalization | Reality |
|---|---|
| "User might prefer option B" | Reversible choice → pick the best one, note it in the report |
| "Asking is safer" | Asking mid-task is the exact failure this mode exists to kill |
| "I did the main part" | Partial delivery = not done. Docs/tests/verify are part of the task |
| "Tool failed, so I'll report and stop" | Failure handling is YOUR job: retry, fallback, alternative route |

Destructive/irreversible/paid actions still require approval — that's a batched-upfront question or a legitimate hard block, never silently skipped.
