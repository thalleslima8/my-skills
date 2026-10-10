# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.10.0] - 2026-10-10

Driven by the transcripts of real `/flow` runs. The spike was not called too often; the cost was the loop implementation → gate → fix → gate, which existed because the spike was judged against rules it had never been given. In one measured epic, two fix rounds for four findings in test fixtures and a changelog cost more input tokens than the implementation and its first gate together. Everything ran on the session's model, the spike received seven phases in one call and filled its context window, and the orchestrating session grew past 250k tokens.

### Added

- `spike` **agent** (`plugins/workflow/agents/spike.md`), `/flow`'s implementer in execution mode. It replaces calling a general-purpose sub-agent with the `/spike` command's file, which loaded every mode of the command on each call. It declares `model: opus`.
  - **Rule register before coding:** it reads the standards sources `/flow` passes (`CLAUDE.md`, `docs/standards/` by scope, the glossary as naming rules for code, tests, fixtures and docs, accepted ADRs, the `DA-###` in force, contributing guides, the pull request template) and lists every rule that binds the slice, obligations included.
  - **Definition of done before every `DONE`**, run over the whole change: rules by class (every occurrence, not the first), obligations present and consistent with the text around them, factual claims in docs, changelogs, comments and test names checked against the repository, acceptance items mapped to code and tests, leftovers, and the CI's own commands on the whole suite.
  - The `DONE` block carries the evidence: `Rules`, `Obligations`, `Claims`, `Gaps` and `Verify`.
  - Fix rounds of kind `review` are fixed by class of finding; a new kind, `polish`, takes the non-blocking findings, which the spike fixes or declines with a reason.
  - On a question it goes on with what does not depend on it and gathers every foreseeable question into one `BLOCKED` block. It never stages (`git add`, `git reset`, `git stash`): the index is `/flow`'s review snapshot.
- `flow-execution` **skill**: `/flow`'s execution mode, moved out of the command so a mediation session does not carry its rules. The `/flow` command loads it when a run starts (`user-invocable: false`; never started on its own).
- `scripts/usage-report.ps1` (PowerShell 7): reads a project's local Claude Code transcripts and reports, per session and per kind of sub-agent, the calls, the largest context reached and the input tokens spent; `-Detail` shows one session's context timeline and tool sizes. `README.md` and `docs/CONTRIBUTING.md` say what to compare before and after a workflow change.

### Changed

- `/flow` execution mode (now in the `flow-execution` skill):
  - **Models:** every call names its model or takes it from its agent definition, so a run no longer costs what the session's model costs. The session itself works on `sonnet`.
  - **Pre-flight:** a run starts in a session that carries nothing else (a session that already ran a mediation is refused unless the user says to run there). The standards sources are collected once per run and the verification commands are read from the CI workflows; both go to every spike call (`[STANDARDS SOURCES]`, `[VERIFY]`).
  - **Slices:** `/flow` decides how much the spike gets per call — at most 3 pending phases or 12 pending items — instead of leaving it to the spike's sense of its own context. Earlier slices' summaries go in `[PREVIOUS SLICES]`; the last slice writes the epic's commit message. `HANDOFF` stays as a safety valve.
  - **Continuing the same agent:** answers to a `BLOCKED`, review fix rounds and polish rounds continue the spike that did the work (`SendMessage`) instead of starting a new one from a cold context.
  - **Review gate:** `/flow` checks the `DONE` block's evidence before spending a review. The first gate reviews the whole epic; then `/flow` stages everything, and every later gate is a delta gate. Fix requests ask for a sweep by class. A finding in code the fix round did not touch is a late finding and never blocks.
  - **Polish round:** once per commit, after the gate passes, the non-blocking findings (MAY, baseline, Spec and claims, late findings) go to the spike before the commit, instead of going to the pull request and coming back as a comment round. What is declined or left open still goes to the pull request.
  - **Session budget:** at each epic boundary, 12 or more agent calls in the session pause the run for a new session to resume. A count replaces "when the session is heavy". A pull request comment round runs in a session of its own, and uses the comments as the gate's spec.
- `/flow` command: holds mode detection, mediation and the rules common to both modes, and loads `flow-execution` for a run. Code evidence for a mediation comes from a read-only sub-agent with a self-contained brief on `sonnet`, no longer from the `/spike` command's file. The "getting heavy" warning is decided by a count (12 agent calls or 3 trees), at the end of a point.
- `/spike` command: the "Mode: Epic implementation under /flow" section is gone (the `spike` agent replaces it). New mandatory "Rule register and definition of done" section, wired into epic implementation, direct implementation and bug fixes; the whole test suite replaces "or the affected subset".
- `code-review` skill (adapted from [mattpocock/skills](https://github.com/mattpocock/skills), MIT; the `LICENSE` and attribution are kept). Modifications in this version:
  - The Standards sub-agent reports violations by rule: one finding lists every location of that rule in the change.
  - The Spec sub-agent also reports **claims**: factual statements the change makes that the repository contradicts, with statements about external systems marked `unconfirmed`. The report gets a "Claims" subsection.
  - Both sub-agents are called with `model: "sonnet"` unless the user asks otherwise.
  - Gate mode: the standards sources come from `/flow` instead of being collected at every gate; a new **delta gate** for every gate after an epic's first (open findings confirmed across the whole change, new findings only in the delta, the Spec sub-agent only when there are Spec items to confirm, late findings never blocking); non-blocking findings go to `/flow`'s polish round before the pull request.
- `design-an-interface` skill (adapted from [mattpocock/skills](https://github.com/mattpocock/skills), MIT; the `LICENSE` and attribution are kept). Modification: the design sub-agents are called with `model: "sonnet"` unless the user asks otherwise.
- `arquiteto` and `analyst` agents: `model: sonnet` and `tools: Read, Glob, Grep`. They give opinions and write nothing, so they no longer inherit the session's model nor every tool.
- `conventional-commit` and `test-failure-triage` skills, `/infra`, `README.md` and `docs/CONTRIBUTING.md` refer to the `spike` agent where they described `/spike` as `/flow`'s sub-agent. `docs/CONTRIBUTING.md` gains "Keeping a command light" and "Measuring a workflow change".
- `workflow` plugin version `0.9.0` → `0.10.0`; marketplace version `0.9.0` → `0.10.0`.

### Upgrade notes

- A project without `docs/standards/` gives the gate only unlevelled rules, and every unlevelled documented rule blocks as "important". Writing the project's rules there with IDs and MUST / SHOULD / MAY levels makes the gate predictable.
- Ask `/flow` to implement in a new session, and start another one for the pull request comment round.

## [0.9.0] - 2026-10-03

### Added

- `/flow` **execution mode**, entered only on an explicit request to implement; mediation mode is unchanged and stays the default. The goal is to take the user out of the spike ↔ flow loop between planning and review.
  - **Scope and order:** with no argument, every epic in `in-progress/` and then in `backlog/`; with an argument, only the epics named. In-progress epics come first, then the backlog. Inside each folder, epics follow their declared dependencies (`Depends on:`), or, when none are declared, an ordering round with the architect and the analyst under the mediation round rules. The order is not submitted for approval; it goes into the pull request description.
  - **Pre-flight:** a clean working tree (or a run being resumed), `gh` authenticated, the default branch, and the CI triggers read from `.github/workflows/` as a fact: push CI, PR-only CI or no CI.
  - **Git:** one `flow/<yyyy-mm-dd>` branch from the default branch per run; one commit per epic, made by `/flow` (never by `/spike`) with a conventional-commit message whose body explains why, carries `Epic: {slug}` and records everything the pull request description needs from that epic (the `DA-###` with provisional ones marked, accepted SHOULD deviations, non-blocking findings and Spec findings); a push after each commit; never a force-push. A single pull request for the whole run, opened as draft on the first push when CI only runs on `pull_request` and marked ready at the end, or opened at the end when CI runs on `push`.
  - **CI:** validated after every push (`gh pr checks --watch` or `gh run watch`). A flaky or infra failure gets one re-run before it counts; a real failure goes to `/spike` with `test-failure-triage` and comes back as an extra `fix(...)` commit that references the epic.
  - **`/spike` as a sub-agent:** called with `spike.md` prefixed, the epic's pending phases, the `DA-###` in force and the answers to earlier blocks. It returns exactly one block: `DONE` (summary, tests, commit message), `BLOCKED` (questions of kind `question`, `divergence`, `interface` or `rule-change`, with context and `file:line`) or `HANDOFF` (at a phase boundary when its context is heavy). The epic's `- [x]` checklist is the source of truth for where to resume.
  - **Questions:** resolved with the architect and the analyst under the mediation rules (independent rounds, at most 1 counter-argument per question). A question is critical when it blocks the epic, is the user's to decide or is hard to reverse. A critical question without consensus stops the run. A non-critical one without consensus is decided by the area's specialist (architect for technical questions, analyst for functional ones) and recorded as a provisional `DA-###`, listed in the pull request for the user to confirm or revert.
  - **Frontend interfaces:** `design-an-interface` runs in `/flow`'s session (it spawns sub-agents, which `/spike` cannot as a sub-agent); the architect picks, the analyst validates, and the choice becomes a `DA-###`.
  - **Review gate:** `code-review` runs in `/flow`'s session for each epic before its commit, on `git diff HEAD` plus untracked files. Approval means the code follows the project's standards: a violated MUST rule blocks unless excepted by a `DA-###` or ADR citing the rule ID, and a violated SHOULD rule blocks unless the architect accepts the spike's reason. MAY findings, baseline smells, `not verifiable` rules and the Spec axis (information only) go to the pull request. Contested findings are arbitrated in one round (architect for standards, analyst for spec). At most 2 fix rounds per epic, counted separately for the review and for CI; the third failure stops the run.
  - **Single checkpoint:** with every epic committed and CI green, `/flow` opens the pull request (or marks it ready) and stops. The description carries the order and its reason, one commit per epic, the `DA-###` settled during the run with the provisional ones highlighted, justified SHOULD deviations, MAY and baseline findings, unverifiable rules, Spec findings and CI status.
  - **Comment rounds:** only when the user says so, never by polling. `/flow` fetches only the unresolved review threads (`gh api graphql` with `isResolved`), the review bodies and the general comments. `/spike` fixes, `code-review` runs again on the correction, and a comment that contradicts a project standard is flagged in its thread instead of being applied silently. Each round is one commit, then a push and a CI check, and `/flow` replies in each thread with the commit SHA without resolving it. The merge is the user's, and `/flow` ends when the user says the pull request is approved.
  - **Stop and resume:** epics already approved stay committed and pushed, and the stopped epic's partial work stays uncommitted in the working tree. `/flow` writes the open question into the epic as a pending decision and hands the user a brief. A new `/flow` request to implement, in a new session, rebuilds the state from the epics' checklists, the `flow/*` branch (including the epic commit bodies) and the open pull request, with no extra state file. In execution mode the "session is getting heavy" warning stops at an epic boundary and says so.
- `/spike`: a "Mode: Epic implementation under /flow" section, used only when `/flow`'s execution mode calls it, with explicit overrides. The call itself is the explicit request to implement. It still never commits or pushes, but now hands the message to `/flow`. Bug fixes and investigations need no confirmation. Interface choices, divergences, questions and category B rule changes go back as `BLOCKED`, the context warning becomes a `HANDOFF`, and it never runs `code-review` or `design-an-interface` (they spawn sub-agents).

### Changed

- `code-review` skill (adapted from [mattpocock/skills](https://github.com/mattpocock/skills), MIT; the `LICENSE` and attribution are kept). Modifications in this version:
  - `docs/standards/` at the project root is stated as the **primary source** of the review when the project uses that convention, and its format is documented: a `README.md` index with a table of file, prefix and scope (`GEN` general, `BE` backend, `FE` frontend, `API` REST, `DB` database); rules with stable IDs (`GEN-001`); MUST / SHOULD / MAY levels (DEVE / DEVERIA / PODE); the precedence order legal/security/compliance > `DA-###` and ADRs > `CLAUDE.md` > standards > idiomatic conventions; MUST exceptions recorded as a `DA-###` citing the rule ID; SHOULD deviations justified in the PR (and treated as `excepted` when reviewing a PR that justifies them); removed rules as `~~ID~~ (removed: reason)`. The report says when the project has no `docs/standards/`.
  - New **gate mode** for `/flow`'s execution mode: run in `/flow`'s own session, fixed scope (`git diff HEAD` plus untracked files), the epic as spec with no question to the user, findings numbered `F1…`, no closing question, and a `Gate` section with a pass/fail verdict. A violated MUST blocks unless excepted, a violated SHOULD blocks unless the architect accepted a reason, and MAY findings, baseline smells, `not verifiable` rules and the Spec axis never block. `/flow`'s limit of 2 fix rounds replaces "Do not loop" in this mode.
- `design-an-interface` skill (adapted from [mattpocock/skills](https://github.com/mattpocock/skills), MIT; the `LICENSE` and attribution are kept). Modification: an "Under /flow's execution mode" section. `/flow` runs the skill in its own session, the framing goes to the architect, `/flow` gives no recommendation, the architect picks, the analyst validates (one counter-argument, then the architect's choice stands as provisional unless the question is critical) and the choice is recorded as a `DA-###`.
- `conventional-commit` skill: states who runs the commit. The user does everywhere except in `/flow`'s execution mode, where `/flow` commits the message `/spike` wrote and adds to the body what the pull request description needs from the epic (decisions, accepted SHOULD deviations, non-blocking and Spec findings). The body lists the `DA-###` an epic commit applies.
- `test-failure-triage` skill: under `/flow`'s execution mode, category B goes back to `/flow` as a `BLOCKED` `rule-change` and is settled by the architect and the analyst like any other blocked question; category C in CI gets one re-run.
- `arquiteto` and `analyst` agents: they answer any `/flow` prompt that ends in a `[TASK]` in the format it asks for, which now covers ordering, blocked questions, provisional decisions, arbitration of contested findings, interface choice and validation, and rule-change checks. Their descriptions mention the execution-mode roles.
- `/infra`, `README.md` and `docs/CONTRIBUTING.md` describe the two `/flow` modes and `/spike` as `/flow`'s sub-agent.
- `workflow` plugin version `0.8.0` → `0.9.0`; marketplace version `0.8.0` → `0.9.0`.

## [0.8.0] - 2026-10-03

### Added

- `design-an-interface` skill in the `workflow` plugin, adapted for frontend modules from the upstream skill of the same name in [mattpocock/skills](https://github.com/mattpocock/skills) at `f958fa17c1b6` (MIT, Copyright (c) 2026 Matt Pocock), the last commit before upstream removed it (`c66bdee`) and absorbed its technique into `codebase-design` as `DESIGN-IT-TWICE.md`. The upstream `LICENSE` ships next to the skill.
  - Kept from upstream: "design it twice", requirements gathered first, 3+ parallel sub-agents each under a different constraint and forced to differ radically, designs presented one at a time and then compared in prose (simplicity, depth, general-purpose versus specialized, ease of correct use), no judging by implementation effort, and no implementation.
  - Taken from the successor `DESIGN-IT-TWICE.md`: a short framing of the problem shown to the user before the sub-agents start, invariants and error modes as part of the interface, and an opinionated recommendation (or hybrid) at the end.
  - Changed: scoped to frontend module interfaces (component props, children, slots and events; hook or composable arguments and return values; client stores; client API and data-fetching modules), with the "interface ≠ visual UI" distinction spelled out. It fires on its own when frontend work creates or changes such an interface and says why it skips otherwise (styling, markup, internal changes, private subcomponents, an interface already decided in a `DA-###`, an ADR or earlier in the session). Requirements are looked up in the callers and in existing modules of the same kind before asking. Every design is bound by the project's frontend rules (`CLAUDE.md`, `docs/standards/` by rule ID), and a design that breaks a mandatory rule is dropped. The sub-agent constraints are frontend ones (minimal interface, composition, common case first, house pattern / UI library idioms), each design states who owns accessibility, and the comparison adds accessibility, rendering cost, testability through the interface and fit with the codebase. Sub-agents may not edit files, invoke the skill or spawn agents. The chosen interface is restated as the reference for implementation, with an ADR offered through `domain-modeling` when the choice qualifies.

### Changed

- `/spike` gets a mandatory "Frontend interfaces" rule: before writing frontend code, it checks whether the work creates or changes a frontend module's interface and, if so, runs `design-an-interface` and implements only after the user picks a design — the one exception to "do not ask whether to start" in direct implementation. Wired into epic implementation, direct implementation and bug fixes (only when the fix has to change an interface).
- `workflow` plugin version `0.7.0` → `0.8.0`; marketplace version `0.7.0` → `0.8.0`.

## [0.7.0] - 2026-10-03

### Added

- `loop-me` skill in the `workflow` plugin, started only with `/loop-me [workflow]` (`disable-model-invocation`). Adapted from the upstream skill of the same name in [mattpocock/skills](https://github.com/mattpocock/skills) at `d81f3a183412` (MIT, Copyright (c) 2026 Matt Pocock), where it sits in the beta `in-progress` bucket. The upstream `LICENSE` ships next to the skill.
  - Kept from upstream: the loop lens, the vocabulary (trigger, checkpoint, push right, brief) used only when a workflow calls for it, "mandate nothing structural", the definition of done (an implementer agent could build the spec without a single question), and the workspace (`workflows/*.md`, `NOTES.md`), with the user's world interviewed first when `NOTES.md` is thin.
  - Changed: it runs on this plugin's `grill-me` (upstream `grilling` was merged into it), without `grill-me`'s docs mode, so it never writes the project's glossary, ADRs or code. It confirms the directory before creating the workspace, reads the existing state at the start of each session, writes each settled decision into the spec in the same turn, keeps unresolved questions in the spec as open so the next session resumes them, deletes or merges a spec only on the user's decision, and never commits. Files are written in the language of the session unless the existing ones use another.

### Changed

- `workflow` plugin version `0.6.0` → `0.7.0`; marketplace version `0.6.0` → `0.7.0`.

## [0.6.0] - 2026-10-03

### Changed

- `code-review` skill in the `workflow` plugin rewritten from a fixed checklist into a review driven by the repository's documented standards, adapted from the upstream skill of the same name in [mattpocock/skills](https://github.com/mattpocock/skills) at `d81f3a183412` (MIT, Copyright (c) 2026 Matt Pocock). The upstream `LICENSE` ships next to the skill.
  - Kept from upstream: two axes (Standards and Spec) in parallel sub-agents, never merged or re-ranked, with a worst issue per axis; the repository overrides the baseline; the Fowler smell baseline as labelled judgement calls; skipping what tooling enforces; failing on a bad ref or an empty diff before spawning anything; "no spec available" instead of inferred requirements.
  - Changed: the Standards sub-agent builds a register of every documented rule that applies to the touched files (`file:line` each) and reports each one as `ok` / `violated` / `not verifiable`; rules that require something (a test, a changelog entry, a doc update) count as violated when it is missing. Standards sources go beyond `CONTRIBUTING.md`/`CODING_STANDARDS.md` to the project's `CLAUDE.md` (read first, and it can point elsewhere), `docs/standards/` (the ai-starter-kit convention: its index is read first and only the files whose scope matches the touched code are used; rules are cited by their stable ID, their level — MUST/SHOULD/MAY or DEVE/DEVERIA/PODE — sets the severity, the declared precedence order settles conflicts, and a breach with a recorded exception such as a `DA-###` naming the rule is reported as `excepted`), nested `CLAUDE.md` files scoped to their subtree, `AGENTS.md`, accepted ADRs, the glossary, other agents' rule files and the PR template; conflicting sources are reported instead of resolved silently. Scope is not limited to a fixed point: a ref, a PR (`gh`), a path, or by default the working-tree changes or the branch against the default branch. Spec sources include the project's epics and `gh issue view`, with no dependency on `docs/agents/issue-tracker.md`. Both sub-agent briefs forbid invoking the skill again or spawning agents (the upstream fan-out bug) and editing files. Findings are verified against their citations before reporting. Severity is critical / important / improvement, taken from the rule's own wording. The previous checklist's error-handling, input-validation, sensitive-data, layering and test items join the baseline as hygiene checks.
- `/spike`'s code review flow now runs the `code-review` skill's process instead of its own steps.
- `workflow` plugin version `0.5.0` → `0.6.0`; marketplace version `0.5.0` → `0.6.0`.

## [0.5.0] - 2026-10-02

### Added

- `grill-me` skill in the `workflow` plugin, started with `/grill-me [docs | no-docs] [topic]` or by `/flow`; its description tells Claude never to start it on its own. It merges `grill-me`, `grill-with-docs` and `grilling` from [mattpocock/skills](https://github.com/mattpocock/skills) at `d81f3a183412` (MIT, Copyright (c) 2026 Matt Pocock); upstream, the first two are one-line wrappers around `grilling` and `domain-modeling`. The upstream `LICENSE` ships next to the skill.
  - Kept from upstream: the design tree worked in rounds (the whole frontier per round, numbered, with a recommended answer), facts looked up through sub-agents without blocking the rest of the round, decisions left to the user, and no action before the user confirms the shared understanding.
  - Changed: one skill with two modes instead of two skills. Docs mode (applies `domain-modeling`) is picked automatically inside a repository and plain (stateless) mode outside one, announced in the first round; `docs` / `no-docs` override it. Questions are asked in the user's language. The skill pushes back once on an answer that looks wrong, keeps "I don't know" as an open decision, sends ungrillable questions to a throwaway prototype (`/spike`), proposes splitting when the scope keeps growing, honors a "one question at a time" rule from `CLAUDE.md`, and never commits. `disable-model-invocation` is not set, so a command can run it; when one does, the command's scope and next step win.
- `domain-modeling` skill in the `workflow` plugin, adapted from the upstream skill of the same name. It triggers on its own when terms are being challenged or defined, when `GLOSSARY.md` is edited, or when an ADR is recorded. `GLOSSARY-FORMAT.md` and `ADR-FORMAT.md` are kept from upstream. Changes: the project's `CLAUDE.md` can name other locations for the glossary and ADRs; read-only personas (`/analyst`, the agents) only propose terms and ADR candidates, and sessions that write docs record them; ADRs are linked both ways to the `DA-###` decisions of `/arquiteto` and `/flow`; files are never committed.

### Changed

- `/flow` now runs on `grill-me`'s design tree, with the specialists (not the user) answering the rounds. Each round puts the whole frontier to the architect and the analyst independently, with a one-line-per-decision `[SETTLED SO FAR]`, since agents keep no memory. The cross-check and the single counter-argument now apply per question (the counter-argument batched in one call per agent). Converged answers settle; a question still diverging after the counter-argument, or one that is the user's alone (goal, priority, budget, acceptable risk, business approval), is parked for the user. The user is asked mid-tree only when a parked question blocks the whole frontier; everything else comes at the end in one summary (consensus + what needs their decision + glossary terms + ADR candidates). Limit of 4 rounds per point, after which `/flow` proposes splitting. Consensus terms go to the glossary through `domain-modeling`, and when formalizing an epic `/flow` offers an ADR for each qualifying `DA-###`.
- `arquiteto` and `analyst` agents: when the prompt is a `/flow` question round, they answer per Q number in the requested format instead of their document/epic format; the architect marks ADR candidates, the analyst proposes canonical terms.
- `/arquiteto` reads the project's glossary at start-up and applies `domain-modeling` (glossary terms, ADRs for qualifying `DA-###` decisions).
- `/analyst` challenges the language against `GLOSSARY.md` (now the one repository file it may read, along with ADR titles) and lists settled terms and ADR candidates in the epic draft for `/flow` to record.
- `workflow` plugin version `0.4.0` → `0.5.0`; marketplace version `0.4.0` → `0.5.0`.

## [0.4.0] - 2026-09-20

### Added

- `api` skill in the `workflow` plugin — an exploratory, Postman/Insomnia-style HTTP client driven by Claude, ported from a project-local skill and made stack-agnostic. A stdlib-only Python runner (`skills/api/scripts/api.py`) builds, authenticates, sends, saves and replays requests; project state lives in `.claude/api/` (`config.json`, `env.local.json`, `requests/`, `.last/`). It complements `/qa` (no verdicts, no reports) and never fixes code (that stays with `/spike`).
  - Commands: `init`, `send`, `run`, `list`, `show`, `env show|set`, `history`, `host status|restart|logs`, `seed`.
  - Behavior kept from the original: `{{name}}` / `{{name|default}}` / `{{$guid}}` / `{{$now}}` substitution that refuses to send a missing variable (and omits a lone optional `{{name}}` in a query value), 2xx-only `--capture` with a mini-JSONPath, secret-free `--save`, output truncation with `--full`, `Retry-After`, `.last/` and `history.jsonl`, key-based secret masking, local-only guardrail with `--allow-remote`, `env.local.json` mode 600, outdated-host warning, exit code 2 with `ERRO: ...` for usage/environment errors.
  - What used to be hard-coded is now configuration in `config.json`: `baseUrl`, `localHosts`, an `auth` map with `defaultAuth`, a `host` block (`cwd`, `start`, `healthUrl`, `processPatterns`, `sourceGlobs`, `sourceIgnore`, `startTimeoutSec`) and a `seed.command` hook that the project provides. The project root comes from `--root`, then `CLAUDE_PROJECT_DIR`, then the nearest `.claude/` or `.git` above the current directory.
  - `init` creates `.claude/api/`, proposes a `host` block from the detected stack (`host.json`, a web `*.csproj`, or a `package.json` `dev` script), updates `.gitignore` idempotently, never overwrites `config.json` without `--force` and leaves an existing `requests/` and `env.local.json` untouched.
  - Hardening over the original: sensitive query-string parameters are masked in the printed URL, in `.last/` and in `history.jsonl`; `--timeout` (default 60 s); redirects are shown but never followed, so a 3xx cannot bypass the local-only guardrail; the saved PID (and its process group) is stopped first, with the PID re-checked against the command line before it is killed, and `processPatterns` as backup; a Windows `taskkill` fallback; `--save` refuses names that escape `requests/` and warns about secret-looking fixed values; `env.local.json` is created with mode 600 from the start; `seed` refuses a non-local `baseUrl` before running the hook and refuses a non-local `baseUrl` in its output.
  - The masking pattern also matches `api-key` (so an `X-Api-Key` header or query parameter is covered), not only `apikey` / `api_key`.
  - Tests (`skills/api/tests/`, stdlib `unittest`): unit tests plus end-to-end tests against a local `http.server`. Run with `python3 -m unittest discover -s plugins/workflow/skills/api/tests -v`.
- `docs/CONTRIBUTING.md` — how to run the tests of a skill that ships code.

### Changed

- `workflow` plugin version `0.3.0` → `0.4.0`; marketplace version `0.3.0` → `0.4.0`.

## [0.3.0] - 2026-09-20

### Added

- `migrate-legacy-claude` skill in the `workflow` plugin — a procedure for moving a project that already has its own `.claude/` (local commands and rules) onto the my-skills plugins. Inventory of every `.claude/` and CLAUDE.md, classification of each local command (A direct equivalent / B partial equivalent / C no equivalent, compared by responsibility, not file name), extraction of the project-specific parts of B commands into the project's `CLAUDE.md` (created from the ai-starter-kit template if missing), then backup, removal of A/B commands, and a non-destructive merge of the marketplace and plugin declarations into `.claude/settings.json`. Always shows a dry-run report and waits for confirmation before any write; C commands are never removed.

### Changed

- `workflow` plugin version `0.1.0` → `0.3.0`; marketplace version `0.2.0` → `0.3.0`.

## [0.2.0] - 2026-09-20

### Added

- `writing` plugin with the `humanizer` skill, adapted from [blader/humanizer](https://github.com/blader/humanizer) v3.0.0 (MIT, Copyright (c) 2025 Siqi Chen). The skill text is kept as upstream; changes are limited to the frontmatter (`upstream` and `upstream-version` metadata instead of `version`) and an attribution line in the "Source" section. The upstream `LICENSE` ships next to the skill.

## [0.1.0] - 2026-09-20

### Added

Initial migration of the command set that lived in `limaj-framework` (`.claude/commands/` and `template-backend/.claude/commands/`) into this repository, decoupled from any specific product and distributed as a plugin marketplace. All content is written in English.

**`workflow` plugin:**
- Commands: `analyst`, `arquiteto`, `flow`, `spike`, `qa`, `infra` — migrated with new frontmatter; `arquiteto`, `infra` and `spike` rewritten to remove product coupling (see "Changed" below); `flow` rewritten to call `arquiteto`/`analyst` as agents instead of reading the command `.md` as a prompt prefix.
- Agents: `arquiteto`, `analyst` — new, extracted from the persona of the commands of the same name, callable via `subagent_type` from `/flow`.
- Skills: `test-failure-triage`, `code-review`, `conventional-commit` — new, extracted from logic that used to be hardcoded inside the original `spike.md` and that now triggers by context, not only when someone types a command.

**`dotnet` plugin:**
- `ef-migrations` skill — new, isolates the rule of applying every EF Core migration to the local database in the same turn it is created (previously hardcoded inside the original `spike.md`).

**Repository:**
- `.claude-plugin/marketplace.json` and one `plugin.json` per plugin.
- `docs/CONTRIBUTING.md` — when to create a command vs. an agent vs. a skill.
- `README.md` — what the repo is, how to install, how to version.

### Changed (product decoupling)

- `spike.md`: the fixed security checklist (ownership via a product-specific identity gateway, BOLA, a product-specific function runner) and the migration rule with hardcoded project paths were replaced by: "apply the security checklist and migration conventions described in the current project's CLAUDE.md; if missing, warn and ask". The test-failure classification protocol and the review checklist were extracted into skills.
- `arquiteto.md`: the fixed infrastructure cost section (consumption plan, free tiers of one specific provider) and the fixed test pyramid (specific framework/mocks) were replaced by references to the project's CLAUDE.md.
- `infra.md`: removed all canonical/mirror copy logic and the sync script (it no longer exists — commands now come from the plugin, not duplicated in the project repo). Responsibility redefined as: project scripts, devcontainer, local tooling and the project's own `.claude/settings.json` — never the contents of installed plugins.
- `flow.md`: the mechanism of "read `arquiteto.md`/`analyst.md` with Read and use it as a prompt prefix" was replaced by direct `Agent(subagent_type: "arquiteto")` / `Agent(subagent_type: "analyst")` calls. The mediation logic (independent opinions, cross-check, one counter-argument round, escalation, epic formalization) is unchanged.
- `analyst.md`, `qa.md`: migrated with minimal adjustment — they were already generic enough.

[0.4.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.4.0
[0.3.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.1.0
