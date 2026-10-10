---
name: code-review
description: Use when the request is to review code rather than implement it — a diff, a branch, a PR, work-in-progress changes, a file or an area, "review since X", "take a look", "find problems". Validates the change against the repository's own documented standards first — docs/standards/ at the project root is the primary source when the project uses that convention, then CLAUDE.md, CONTRIBUTING, coding standards, ADRs, glossary and team rules — checking every applicable rule including the ones that require something to be present, then against the originating spec, and reports both without fixing anything. Also runs as the approval gate of /flow's execution mode (gate mode: blocking verdict, no closing question). Applies regardless of which command or agent is active.
argument-hint: "[ref | PR number | path] [spec path]"
license: MIT
metadata:
  upstream: "https://github.com/mattpocock/skills (skills/engineering/code-review)"
  upstream-commit: "d81f3a183412"
---

# Code review

Review a change along two axes:

- **Standards**: does the code follow the rules this repository and its team have written down?
- **Spec**: does the code do what the originating issue, epic or spec asked for?

The repository is the authority. A generic reviewer flags what is deliberate in a codebase and misses the invariants the codebase depends on. So every documented rule that applies to the change gets checked, the built-in baseline only fills the gaps the documentation leaves, and a documented rule always beats the baseline.

**`docs/standards/` at the project root is the primary source that drives the review**, when the project uses that convention (projects started from the ai-starter-kit always do). Its format is described under "Primary source: `docs/standards/`" below. Without it the review still runs on the other sources, and the report says that the folder is missing.

Both axes run as **parallel sub-agents** so neither sees the other's reasoning. This skill then verifies their findings and reports the two axes side by side.

**Report only. Do not fix anything in this step.** Fixing is a separate round, after the user confirms which findings to act on — or, in gate mode, after `/flow` sends the blocking findings to its `spike` agent (see "Gate mode").

## Process

### 1. Pin the scope

Resolve what is being reviewed, in this order:

1. **A ref the user named** (commit, branch, tag, `main`, `HEAD~5`): `git diff <ref>...HEAD` (three-dot, against the merge-base) and `git log <ref>..HEAD --oneline`. If the working tree also has changes, say so and ask whether to include them.
2. **A PR number or URL**: `gh pr diff <n>` and `gh pr view <n>` for the commit list and description. If `gh` is unavailable, ask for the base branch and fall back to 1.
3. **A path**: review those files (or that directory) as they are now; there is no diff, so every line is in scope.
4. **Nothing named**: if the working tree has changes, review them (`git diff HEAD`, plus untracked files from `git status --porcelain`). Otherwise review the current branch against the merge-base with the default branch. If the current branch *is* the default branch with a clean tree, ask what to review.

In gate mode the scope is fixed: `git diff HEAD` plus the untracked files, with no question about including the working tree.

Before going further, confirm the ref resolves (`git rev-parse`) and the scope is non-empty. A bad ref or an empty diff fails here, not inside two sub-agents. Record the list of touched files: it decides which rules apply.

### 2. Collect the standards sources

Find everything in the repository that says how code should be written. Read the **project's CLAUDE.md first**: it may name other standards files, override the default locations below, or declare that a convention does not apply.

Look for:

- `CLAUDE.md` at the root, in `.claude/`, and in any directory on the path of a touched file (a nested one scopes its rules to its subtree), plus `AGENTS.md` and `CLAUDE.local.md` if present
- **`docs/standards/`, the primary source** (if the project uses that convention). Read its `README.md` index first and pick the files by scope, as described in "Primary source: `docs/standards/`" below. Pass only the files whose scope the touched files fall under, plus the index, and say in the Scope section which ones were left out and why. If the project has no `docs/standards/`, say so in the Scope section
- `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `STYLEGUIDE.md`, `docs/CONTRIBUTING.md` and anything else under `docs/` whose name says standards, conventions, guidelines or style
- ADRs (`docs/adr/` or wherever CLAUDE.md says): an accepted ADR is a rule for the code it covers; a superseded one is not
- The glossary (`GLOSSARY.md` or wherever CLAUDE.md says): canonical domain terms are naming rules
- Other agent rule files the team keeps: `.github/copilot-instructions.md`, `.cursor/rules/`, `.cursorrules`, `.windsurfrules`
- `.github/pull_request_template.md`: its checklist items are obligations
- Linter, formatter and analyzer configs (`.editorconfig`, `eslint`, `ruff`, `.globalconfig`, `Directory.Build.props`, and so on). Do not review against them; note them so the sub-agent skips what tooling already enforces

Pass the list of files found, not their contents. If nothing is found, say so in the report. The Standards axis then runs on the baseline alone, and the report suggests writing the team's rules down.

#### Primary source: `docs/standards/`

When the project keeps its coding rules in `docs/standards/` at the root, that folder is what gives the review its rules. It follows this format:

- **Index.** `docs/standards/README.md` holds a table of the standards files: file, rule prefix and scope. The usual prefixes are `GEN` (general, always applies), `BE` (backend), `FE` (frontend), `API` (REST APIs) and `DB` (database). A file applies when the touched files fall under its scope; the general one always does.
- **Rule IDs.** Every rule has a stable ID made of its file's prefix and a number (`GEN-001`, `API-030`). IDs are never reused. Findings, exceptions and deviations cite rules by ID.
- **Levels.** Every rule has a level: **MUST**, **SHOULD** or **MAY** (written **DEVE**, **DEVERIA** and **PODE** in standards authored in Portuguese).
- **Precedence**, highest first: legal, security and compliance requirements > `DA-###` decisions and ADRs > `CLAUDE.md` > `docs/standards/` > the language's or framework's idiomatic conventions. When the index declares its own order, the index wins.
- **Exceptions to a MUST rule** are recorded as a `DA-###` (in the epic) or an ADR that cites the rule ID and gives the reason. A breach with such a record is `excepted`, not violated.
- **Deviations from a SHOULD rule** are justified in the pull request description. When the review target is a PR, a deviation justified there, citing the rule ID, is `excepted` too; otherwise it is a violation until someone justifies it.
- **Removed rules** stay in the file, struck through: `~~GEN-007~~ (removed: reason)` (or the equivalent word in the standards' language). They are never checked, and their IDs are not reused.

### 3. Find the spec

In gate mode the spec is the epic whose path `/flow` passes; never ask the user. Otherwise, look in this order:

1. A path the user passed as an argument.
2. Issue or PR references in the commit messages or the PR description (`#123`, `Closes #45`, GitLab `!67`), fetched with `gh issue view` / `gh pr view` when available.
3. The epic or spec the project's CLAUDE.md points to, or, if the project uses that convention, an epic under `docs/epics/` that matches the branch or feature.
4. A spec file under `docs/`, `specs/` or `.scratch/` matching the branch or feature name.
5. Ask the user once. If they say there is none, the Spec axis is skipped and the report says "no spec available". Never infer requirements from the code.

### 4. Spawn both sub-agents in parallel

Use two general-purpose sub-agents in the same message, each called with `model: "sonnet"` unless the user asked for another model: checking a change against written rules and a written spec does not need the session's largest model. Each prompt must be self-contained, since the sub-agent has no other access to this skill.

**Standards sub-agent.** The prompt includes the scope command(s) and commit list, the touched files, the standards files from step 2, the tooling configs, the full **baseline** below, and this brief:

> Read the standards files and build a register of every rule that applies to the touched files: a rule is any instruction about how code, tests, docs or commits must be written or organized, including obligations ("every behavior change has a test", "update CHANGELOG.md", "new endpoints are documented"). Cite each rule by its ID when the standards give rules stable IDs (`GEN-004`, `API-030`), otherwise by `file:line`. Record each rule's level when the standards declare levels (MUST / SHOULD / MAY, DEVE / DEVERIA / PODE, or similar). Ignore rules marked as removed (struck through, e.g. `~~GEN-007~~ (removed: reason)`). A rule in a nested file applies only to its subtree. When two sources conflict, use the precedence order the standards declare, if any; otherwise the more specific source wins; if neither is more specific, report the conflict instead of choosing.
>
> Then check the change against every rule in the register. A rule that requires something is violated when the change should contain it and does not. A breach is not a violation when an exception to that rule is recorded the way the standards say exceptions are recorded (for example a `DA-###` decision in an epic or an ADR that names the rule ID and gives the reason for a MUST rule, or a justification citing the rule ID in the PR description for a SHOULD rule): mark it `excepted` and cite the record. Skip anything the listed tooling configs already enforce.
>
> Report violations by rule, not by sighting: when a rule is violated once, search the whole change for every other occurrence of that same rule — source, tests, fixtures and docs — and list all the locations under the one finding. A finding with a single location means you searched and found no other.
>
> Report:
> (a) every violation: the rule (ID or `file:line`, its level, and the rule quoted), every location (`file:line`; quote the hunk of the first, one line for each of the others), why it is a violation, and the fix the rule implies;
> (b) any baseline smell you spot, labelled as a possible smell, with the hunk quoted, unless a documented rule endorses what the smell would flag;
> (c) the register as a compact table: rule, level, source, and status `ok` / `violated` / `excepted` / `not verifiable` (say what would be needed to verify it). Leave out rules that do not apply to the touched files, but give their count.
>
> Documented-rule breaches are hard violations; baseline smells are always judgement calls. Do not invoke the code-review skill or spawn other agents: do this review directly. Do not edit any file. Under 800 words.

**Spec sub-agent.** Skip it if there is no spec. Otherwise the prompt includes the scope command(s) and commit list, the spec's path or fetched contents, and this brief:

> Report: (a) requirements the spec asks for that are missing or partial; (b) behavior in the change that the spec did not ask for (scope creep); (c) requirements that look implemented but where the implementation looks wrong; (d) **claims**: factual statements the change adds or edits in docs, changelogs, comments, test names or messages that the repository contradicts — a version that does not exist (check the tags and the package manifests), a type, member, command or file named wrongly, a compatibility or behavior claim ("no breaking change", "only a warning", "returns 404") that the code or the tests do not bear out, a text that now contradicts its own file. A statement about an external system that the repository cannot confirm is reported as `unconfirmed`, not as wrong. Quote the spec line (or the claim) for each finding and give the code location as `file:line`. Do not invoke the code-review skill or spawn other agents: do this review directly. Do not edit any file. Under 500 words.

### 5. Verify before reporting

Sub-agent output is a hypothesis. For every hard violation and every Spec finding (claims included), open the cited rule and the cited code and confirm both say what the finding claims; for a violation with several locations, confirm the first and spot-check the others. Drop findings whose citation is wrong. Keep a finding you cannot confirm or refute, marked `unverified`. Do not add new findings of your own at this stage, and do not re-rank across axes.

### 6. Report

```
## Scope
<what was reviewed: command, commit count, touched files count>
<standards sources consulted, one line each — or "no docs/standards/ in this project" when it is missing> · <spec source, or "no spec available">

## Standards
### Violations — documented rules
<per finding: [critical|important|improvement] <rule ID>: location — problem — rule (level, quoted; file:line when there is no ID) — fix>
### Judgement calls — baseline
<per finding: [improvement] possible <smell> — location — hunk — suggestion>
### Rule register
<the table from the sub-agent: rule · level · source · status; plus "N rules not applicable">

## Spec
<missing or partial · scope creep · implemented wrong; each with the spec line quoted>
### Claims
<per finding: [wrong|unconfirmed] the statement quoted — location — what contradicts it, or what would confirm it>

## Summary
Standards: <n violations, n judgement calls>; worst: <one line>
Spec: <n findings>; worst: <one line>
```

Severity inside the Standards axis follows the rule's own level or wording. A mandatory rule (MUST / DEVE, never, always, "mandatory", "no exceptions") or one that protects security, data or authorization is **critical**. An expected rule (SHOULD / DEVERIA), or a documented rule with no level, is **important**. A recommendation (MAY / PODE) and a baseline smell are **improvement**. Lead each Standards finding with the rule ID when there is one (`API-030: this 200 should be a 201 with Location`), so the team can find the rule. Never pick a single worst issue across the two axes: a change can pass one and fail the other, and a blended verdict lets the passing axis hide the failing one.

Close by asking which findings, if any, to fix. That becomes a new round. In gate mode, do not ask: end with the Gate section below.

## Gate mode — when `/flow` runs this skill in execution mode

`/flow`'s execution mode uses this review as the approval gate of each epic, before the epic is committed, and again, as a delta gate, after each fix or polish round. `/flow` runs it **in its own session**: the two sub-agents cannot be spawned from inside another sub-agent, so it never runs inside the `spike` agent. In gate mode:

- The scope is `git diff HEAD` plus the untracked files (step 1) and the spec is the epic `/flow` passes (step 3). Nothing is asked.
- Step 2 is not repeated: `/flow` collected the standards sources once, at the start of the run, and passes the list. Pick from it the files whose scope the touched files fall under.
- Steps 4 and 5 run unchanged.
- Number every finding across both axes (`F1`, `F2`, …) so `/flow` and the spike can refer to it.
- The report drops the closing question and ends with:

```
## Gate
Verdict: pass | fail
Blocking: <per finding: F<n> — rule ID (level) — every location — one line>
Non-blocking: <F numbers: MAY findings, baseline judgement calls, Spec findings and claims, late findings; plus the count of `not verifiable` rules>
```

### Delta gate — every gate after the first

The first gate of an epic reviews the whole change. After it, `/flow` stages everything (`git add -A`), so the index holds what was already reviewed and `git diff` shows only what the fix or polish round changed. Every later gate of that epic is a **delta gate**: `/flow` passes the open findings (number, rule, locations) and the deviations the architect accepted, and the review does not start over.

- **Standards sub-agent** — the same brief as step 4, with this in place of its second paragraph: "Open findings: {list}. For each one, confirm the rule has no occurrence left in the whole change (`git diff HEAD` plus the untracked files) and report it `closed` or `still open`, with every remaining location. Then look for new violations **only** in the delta (`git diff` plus the untracked files created since the last gate), building the register only for the rules that apply to the files in the delta. Anything you notice outside the delta goes in a separate list, `late`, one line each. Under 400 words."
- **Spec sub-agent** — runs only when the open findings include Spec or claim items; it confirms those items and reads nothing else. Otherwise it is skipped.
- Step 5 verifies the `still open` and the new findings as usual.
- The verdict fails on an open finding that is still blocking, or on a new blocking violation in the delta. A **late finding** — something in code the round did not touch, which an earlier gate could have reported — never blocks, whatever its level: it is listed as non-blocking and `/flow` sends it to the polish round. Without this, each gate can surface a different part of the same change and the rounds do not converge.

**The approval criterion is that the code follows the project's standards.**

- **Blocks:** a `violated` MUST rule (critical), unless it is `excepted` by a `DA-###` or an ADR that cites the rule ID.
- **Blocks:** a `violated` SHOULD rule, or a documented rule with no level (important), unless `/flow` passes a reason the architect accepted for that finding. It is then a justified deviation, which goes to the pull request description.
- **Does not block:** MAY findings, baseline judgement calls and late findings. After the gate passes, `/flow` sends them to the spike in one polish round; what is left goes to the pull request description.
- **Does not block:** the Spec axis, claims included. It runs on the first gate, and its findings go to the same polish round; what is left goes to the pull request description.
- **Does not block:** `not verifiable` rules. They go straight to the pull request description.
- A blocking finding marked `unverified` still blocks; the spike may contest it.

The gate never fixes anything. `/flow` sends the blocking findings to the spike and owns the rounds: arbitration of contested findings, at most 2 fix rounds per epic, one polish round per commit, and a stop on the third failure. That limit replaces the "Do not loop" note below.

## Baseline

The floor under the repository's rules. It applies only where the documentation is silent: a documented rule always wins, and where the repository endorses something listed here, it is not reported. Every item is a judgement call ("possible Feature Envy"), never a hard violation, and is skipped when tooling already enforces it.

**Code smells** (Fowler, _Refactoring_ ch. 3). Each reads *what it is* → *how to fix*:

- **Mysterious Name**: a function, variable or type whose name does not say what it does or holds, or a domain term that differs from the glossary. → rename it; if no honest name comes, the design is murky.
- **Duplicated Code**: the same logic shape in more than one hunk or file of the change. → extract the shared shape and call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or parameters keep travelling together. → bundle them into one type and pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if` cascade on the same type recurs across the change. → replace it with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split it so each module changes for one reason.
- **Speculative Generality**: abstractions, parameters or hooks added for needs the spec does not have. → delete them; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller should not depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it and call the real target directly.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance and use composition.

**Hygiene**:

- **Unhandled or inconsistent errors**: errors swallowed, or handled differently from how the surrounding code handles them. → follow the error-handling pattern already used next to it.
- **Unvalidated input**: external input (request, file, message, environment) used without validation. → validate it at the boundary.
- **Sensitive data exposure**: secrets, tokens or personal data in logs, error messages or responses. → remove or mask it.
- **Logic in the wrong layer**: business rules in entry points (controllers, endpoints, handlers) or in persistence code, when the code around it keeps them elsewhere. → move the rule to where its neighbors keep theirs.
- **Untested behavior change**: changed or new behavior with no matching test change, or tests that cover only the happy path. → add tests for the invalid and edge cases.

## Notes

- **Fresh context reviews better.** A session that just wrote the code shares every assumption that shaped it. When the review follows an implementation in the same session, say so in the report's Scope section.
- **Do not loop.** Judgement calls are not deterministic between runs and fixes create new surface. Treat a pass as a list of leads, act on the ones with a cited rule behind them, and stop.
- **Missing rules are a finding about the docs, not the code.** If the review keeps raising the same baseline smell and the team agrees with it, suggest writing it into the project's standards so the next review checks it as a rule.
