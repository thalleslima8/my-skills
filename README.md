# my-skills

A personal plugin marketplace for [Claude Code](https://claude.com/claude-code): versioned commands, agents and skills that can be reused in any project — without duplicating files inside each repository.

This repository exists because commands such as `/analyst`, `/arquiteto`, `/flow`, `/spike`, `/qa` and `/infra` used to be copied into every product repository (one canonical copy plus a mirror). That meant drift between copies, no independent versioning of the workflow, and coupling between the *process* and the *stack* of one specific product. Here, the process becomes an installable plugin, and each project only carries its own conventions in its own `CLAUDE.md`.

## Core rule: generic process here, project convention in each repo's CLAUDE.md

Nothing in this repository should know the name, stack or conventions of a specific product. The commands, agents and skills here ask generic questions ("what is this project's test stack?", "what is this project's infrastructure cost sensitivity?") and read the answer from the `CLAUDE.md` of the repository they are running in. If `CLAUDE.md` lacks the required section, the expected behavior is to ask before assuming — never to inherit a value from another product.

In practice: any improvement to the **process** (a new bug-triage protocol, a new review checklist) lands here. Any **product** convention (layer names, test framework, infra cost policy) lands in the `CLAUDE.md` of the project that uses the plugin.

## What is in here

### `workflow` plugin

Commands (invoked explicitly with `/`):

| Command | Role |
|---|---|
| `/analyst` | Functional and domain analysis — challenges the proposal before validating it, maps edge cases and legal/compliance risks. Produces an epic draft. |
| `/arquiteto` | Technical design, stack, TDD, security/DevSecOps. Produces Markdown documentation only. |
| `/flow` | Mediates between `/arquiteto` and `/analyst` — grills the two specialists (not the user) on the point in rounds, using `grill-me`'s design tree: independent answers per round, cross-check per question, at most one counter-argument per question. The user only gets the remaining conflicts and the decisions that are theirs alone. Formalizes the consensus as an epic. **Execution mode** (only on an explicit request to implement, in a session of its own; its rules live in the `flow-execution` skill, loaded only then): drives the `spike` agent, the architect and the analyst through the epics (`in-progress/` first, then `backlog/` ordered by dependency, or only the epics named) with no user in the loop. The spike gets slices of at most 3 phases, together with the project's standards sources and the commands its CI runs. Questions the spike cannot decide go to the specialists (a critical one with no consensus stops the run; a non-critical one is decided by the area's specialist as a provisional `DA-###`). Each epic passes the `code-review` gate once (the project's standards decide): fix rounds go by class of finding and are re-checked on the delta only, and one polish round fixes the non-blocking findings before the commit. `/flow` makes one commit per epic on a `flow/<yyyy-mm-dd>` branch, validates CI on GitHub after each push, pauses at an epic boundary after 12 agent calls in the session and stops at a single pull request. Review comments are handled in rounds, in a new session, when you say so; the merge is always yours. A paused or stopped run resumes from the epics' checklists, the branch and the pull request. |
| `/spike` | The only command that touches product code — investigates, implements, fixes bugs and reviews. Before coding it builds a register of the rules the repository documents, and before delivering it runs a definition of done (rules by class, obligations, factual claims, acceptance, leftovers, the whole test suite). On frontend work that creates or changes a module's interface, it runs `design-an-interface` and waits for the user to pick a design before implementing. Under `/flow`'s execution mode the implementer is the `spike` agent below, not this command. |
| `/qa` | Independent test execution, driven by epics/documentation/code. |
| `/infra` | Local development infrastructure of the current project (scripts, devcontainer, the project's own `.claude/settings.json`). |

Agents (callable via `Agent(subagent_type: "...")`, used internally by `/flow`):

- `arquiteto` — same persona as the command, as an isolated opinion. In `/flow`'s execution mode it also orders epics, picks frontend interfaces and arbitrates contested standards findings.
- `analyst` — same persona as the command, as an isolated opinion. In `/flow`'s execution mode it also validates the chosen interfaces, checks rule changes against the epic and arbitrates contested spec findings.
- `spike` — `/flow`'s implementer in execution mode. It receives one slice of an epic (or a fix round), builds the rule register from the standards sources `/flow` passes, implements, runs the definition of done and returns one `DONE`, `BLOCKED` or `HANDOFF` block. It never commits, stages or asks the user.

Each agent declares its model (`arquiteto` and `analyst` run on `sonnet` with read-only tools, `spike` on `opus`), and the review and design sub-agents are called on `sonnet`, so the cost of a `/flow` session does not follow the model the session itself uses.

Skills (trigger on their own based on context, no command needed):

- `test-failure-triage` — protocol for classifying a failing existing test (real regression / rule changed / flaky).
- `code-review` — stack-agnostic review on two axes, run as parallel sub-agents: **Standards** (does the change follow the rules the repository documents — `docs/standards/`, CLAUDE.md, CONTRIBUTING, coding standards, ADRs, glossary, other agents' rule files, the PR template?) and **Spec** (does it do what the issue or epic asked?). The project's rules are the authority: every applicable rule is checked and listed in a rule register with its status, rules that require something (a test, a changelog entry) count as violated when it is missing, and a built-in baseline (Fowler code smells plus basic hygiene) only covers what the docs leave out. `docs/standards/` at the project root is the primary source when the project uses that convention: an index of files by prefix and scope (`GEN`, `BE`, `FE`, `API`, `DB`), rules with stable IDs and MUST/SHOULD/MAY levels (DEVE/DEVERIA/PODE), a declared precedence order, MUST exceptions recorded as a `DA-###` citing the rule ID, SHOULD deviations justified in the PR, and removed rules struck through; the report says when the folder is missing. Findings are verified against their citations before being reported; nothing is fixed in the same step. A violated rule is reported once with every location it was found at, and the Spec axis also checks the factual claims the change makes in docs, changelogs, comments and test names (a version that does not exist, a compatibility claim the code does not bear out). In **gate mode** (`/flow`'s execution mode) it returns a pass/fail verdict instead of a closing question: a violated MUST blocks unless excepted, a violated SHOULD blocks unless the architect accepts a reason, and MAY findings, baseline smells and the Spec axis go to one polish round and then to the pull request description. After an epic's first gate every gate is a **delta gate**: it confirms the open findings and looks for new ones only in what the fix round changed, so the rounds converge. Invoke it as `/workflow:code-review` to avoid Claude Code's built-in `/code-review`, which hunts bugs instead. Adapted from Matt Pocock's [code-review](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock); the original license is kept next to the skill.
- `conventional-commit` — commit message convention (`feat`/`fix`/etc.). It only writes the message; the user commits, except in `/flow`'s execution mode, where `/flow` commits the message `/spike` wrote.
- `api` — exploratory Postman/Insomnia-style HTTP client for the project's local API, driven by Claude: send a request, chain calls by capturing response fields, save and replay requests, start/restart the local dev server, run the project's own seed hook. Complements `/qa` (no verdicts or reports) and never fixes code. Everything project-specific — base URL, auth headers, how to start the host, the seed command — is configuration in the project's `.claude/api/config.json`, created by `api init`; the runner is stdlib-only Python 3 (`python3`, `python` or `py -3`) and runs where the API runs, e.g. inside the Dev Container.
- `migrate-legacy-claude` — migrates an existing project that has its own `.claude/` (local commands and rules) to these plugins without losing anything project-specific: inventories the local commands, classifies each as direct equivalent / partial equivalent / no equivalent, moves the project-specific parts to `CLAUDE.md`, backs up `.claude/`, removes only the replaced commands and declares the marketplace in `.claude/settings.json`. Shows a dry-run report and waits for confirmation before changing anything. Use it on an old project; for a new/empty one, start from the ai-starter-kit instead.
- `design-an-interface` — "design it twice" (Ousterhout) for frontend modules: when a change creates or changes the interface of a component (props, children, slots, events), hook or composable, client store or client API module, 3–4 parallel sub-agents each design a radically different interface under a different constraint (minimal, composable, common-case first, house pattern), all bound by the project's frontend rules (`CLAUDE.md`, `docs/standards/`). The designs are compared on depth, ease of correct use, accessibility, rendering cost, testability and fit with the codebase, one is recommended, and the user picks before anything is implemented. `/spike` runs it on every frontend change that touches an interface, and skips it for styling, markup, internal changes or an interface already decided. Under `/flow`'s execution mode, `/flow` runs it in its own session (it spawns sub-agents, which `/spike` cannot there), the architect picks, the analyst validates and the choice becomes a `DA-###`. Adapted from Matt Pocock's [design-an-interface](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock), since removed upstream in favor of `codebase-design`; the original license is kept next to the skill.
- `domain-modeling` — builds the project's domain model while a design is discussed: challenges terms against `GLOSSARY.md` and the code, writes resolved terms to the glossary as they settle, and offers an ADR only for decisions that are hard to reverse, surprising without context and a real trade-off (linked both ways to the `DA-###` decision of `/arquiteto`/`/flow`). Locations default to `GLOSSARY.md` and `docs/adr/` and can be overridden in the project's `CLAUDE.md`. Read-only personas (`/analyst`, the agents) only propose; sessions that write docs record. Used by `/grill-me`, `/flow`, `/arquiteto` and `/analyst`. Adapted from Matt Pocock's [domain-modeling](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock); the original license is kept next to the skill.

Skill started by the user (`/grill-me`) or by `/flow`, never on its own:

- `/grill-me` — a relentless interview that turns a loose idea, plan or decision into a shared understanding. It works a design tree in rounds: each round asks every question whose prerequisites are already settled, numbered, with a recommended answer, and looks facts up itself instead of asking for them. Inside a repository it runs in **docs mode** and applies `domain-modeling` as it goes; outside a repository, or with `no-docs`, it writes nothing. Ends with a summary to confirm. `/flow` uses it as its engine, with the rounds put to the architect and analyst agents instead of the user. Merges Matt Pocock's [grill-me and grill-with-docs](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock); the original license is kept next to the skill.

Skill loaded only by the `/flow` command:

- `flow-execution` — the rules of `/flow`'s execution mode (pre-flight, order, spike slices, review gate, polish, commit, CI, pull request, comment rounds, stop and resume). It is a separate skill so a mediation session does not carry them; `/flow` loads it when a run starts.

Skill started only by the user:

- `/loop-me` — grills you, over as many sessions as it takes, into **workflow** specs: one per recurring loop in your life or work (your morning, your week, triaging a channel) that is worth delegating. Uses `grill-me`'s rounds with a small vocabulary (trigger, checkpoint, push right, brief) and mandates no structure. A spec is done when an implementer agent could build it without asking a single question. The current directory is the workspace: `workflows/*.md` (one spec per workflow) and `NOTES.md` (your tools, channels and terminology); it confirms the directory before creating them. Adapted from Matt Pocock's [loop-me](https://github.com/mattpocock/skills) (MIT, Copyright (c) 2026 Matt Pocock), still a beta skill upstream; the original license is kept next to the skill.

### `dotnet` plugin

Stack-specific skills — only relevant to projects using that technology:

- `ef-migrations` — every EF Core migration created is applied to the local database in the same turn.

### `writing` plugin

Skills for editing prose, independent of any code stack:

- `humanizer` — rewrites AI-sounding text so it reads like the writer without changing what it says. Adapted from [blader/humanizer](https://github.com/blader/humanizer) (MIT, Copyright (c) 2025 Siqi Chen); the original license is kept next to the skill.

## Installation

```
/plugin marketplace add thalleslima8/my-skills
/plugin install workflow@my-skills
/plugin install dotnet@my-skills
/plugin install writing@my-skills
```

Install `dotnet@my-skills` only in projects that actually use .NET/EF Core — the `workflow` plugin does not depend on it. `writing@my-skills` is standalone and can be installed anywhere.

## New project vs. existing project

This repository is complementary to [ai-starter-kit](https://github.com/thalleslima8/ai-starter-kit): this one holds the *process* (plugins), the starter kit holds the per-project *layer* (`.claude/settings.json` declaring this marketplace, plus a `CLAUDE.md` template with placeholders).

- **New project** — start from the ai-starter-kit and follow its README. The `settings.json` it ships already enables the `workflow` plugin; you only fill in `CLAUDE.md`.
- **Existing project with its own `.claude/`** — migrate it with the `migrate-legacy-claude` skill, as described below.

### Adopting in an existing project

1. **Install the plugin first.** The migration skill ships inside `workflow`, so it must be available before the project is migrated:
   ```
   /plugin marketplace add thalleslima8/my-skills
   /plugin install workflow@my-skills
   ```
2. **Ask for the migration** inside the project, e.g. "migrate this project to my-skills". The skill triggers on its own.
3. **Review the dry-run report.** Nothing is changed yet. The skill inventories every local command and classifies it as **A** (direct equivalent), **B** (partial equivalent with project rules mixed in) or **C** (project-only automation, never removed). It shows which project-specific passages will move to `CLAUDE.md` and under which section, and asks about anything ambiguous.
4. **Confirm the plan.** Only then does the skill:
   - back up the whole `.claude/` (and the original `CLAUDE.md`) to `.claude.bak-<YYYY-MM-DD>/`;
   - write the extracted passages into `CLAUDE.md` and verify each one landed;
   - merge `extraKnownMarketplaces` and `enabledPlugins` into `.claude/settings.json` without touching permissions, hooks or env (adding `dotnet@my-skills` for .NET/EF Core projects);
   - remove only the A and B command files.
5. **Finish by hand.** Restart Claude Code in the project and check that the plugin commands (`/spike`, `/qa`, …) resolve. Decide whether to gitignore or commit the backup, then commit — the skill never commits.

After the migration the project's `.claude/` keeps only what is its own: `settings.json`, category C commands, local agents/skills and project config such as `.claude/api/`.

## Versioning

- One tag per improvement (e.g. `v0.2.0` when a new skill or flow adjustment is added) — no scheduled releases, no batching unrelated changes under one tag.
- `CHANGELOG.md` records what changed in each version, following [Keep a Changelog](https://keepachangelog.com/).
- The `version` in `.claude-plugin/marketplace.json` and in each `plugin.json` tracks the latest tag that touched that plugin.

## Measuring a change

`scripts/usage-report.ps1` (PowerShell 7) reads a project's local Claude Code transcripts and reports, per session and per kind of sub-agent, the calls made, the largest context reached and the input tokens spent. Run it on a project before and after a change to the workflow to see whether the change paid off:

```
pwsh scripts/usage-report.ps1 -Project <part of the project folder name> -Days 7
```

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for what to compare.

## Contributing

Before adding something new, read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — it explains when something should be a command, an agent or a skill. All content in this repository is written in English.
