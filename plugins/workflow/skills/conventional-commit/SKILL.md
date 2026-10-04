---
name: conventional-commit
description: Use whenever generating a commit message for a finished code change — follows the Conventional Commits format (feat/fix/etc.), in English. Triggers automatically at the end of any implementation, fix or refactor, regardless of which command or agent is active. Never runs the commit itself — only produces the message; the one exception is /flow's execution mode, where /flow runs the commit with the message /spike produced.
---

# Commit message convention

When generating a commit message for a code change, follow the [Conventional Commits](https://www.conventionalcommits.org/) format, always in English, even if the conversation is in another language:

```
type(scope): short description in the imperative mood
```

## Types

| Type | When to use |
|---|---|
| `feat` | New functionality visible to whoever uses the software |
| `fix` | Bug fix |
| `refactor` | Internal structure change with no observable behavior change |
| `test` | Adding or adjusting tests, with no production code change |
| `docs` | Documentation |
| `chore` | Maintenance, dependencies, tooling, configuration |
| `perf` | Performance improvement with no behavior change |

## Rules

- First line in English, imperative mood ("add", "fix", "remove" — not "added", "fixes", "removed")
- Scope in parentheses when it helps isolate the affected module/layer — e.g. `fix(auth): ...`
- If the change implements a tracked epic or issue, reference its identifier/slug in the commit body (e.g. `Epic: {slug}`), and list the `DA-###` decisions it applies when the epic records them
- The commit body (when needed) explains the "why" of the change, not the diff line by line
- For a bug fix, the minimum accepted format is `fix(scope): short description`
- **Never run the commit yourself** — produce the ready message and wait for the user to confirm/run `git commit`, unless explicitly told otherwise

## Who runs the commit

| Context | Who writes the message | Who runs `git commit` |
|---|---|---|
| Any session, including `/spike` called by the user | The session | The user |
| `/flow` in execution mode | `/spike`, in its `DONE` block | `/flow` — one commit per epic, plus one commit (usually `fix(...)`) per CI fix round and per pull request comment round, each referencing the epic's slug and followed by a push |

In `/flow`'s execution mode, `/flow` checks the message against these rules before committing and adds to an epic commit's body everything the pull request description needs from that epic: the `DA-###` (provisional ones marked), the SHOULD-rule deviations the architect accepted (`Deviations: {rule ID} — {reason}`), the non-blocking review findings (MAY, baseline, `not verifiable`) and the Spec findings. `/spike` never commits or pushes, in any mode.
