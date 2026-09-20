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
| `/flow` | Mediates between `/arquiteto` and `/analyst` — independent opinions, cross-check, at most one counter-argument round, escalation to the user if the conflict persists. Formalizes the consensus as an epic. |
| `/spike` | The only command that touches product code — investigates, implements, fixes bugs and reviews. |
| `/qa` | Independent test execution, driven by epics/documentation/code. |
| `/infra` | Local development infrastructure of the current project (scripts, devcontainer, the project's own `.claude/settings.json`). |

Agents (callable via `Agent(subagent_type: "...")`, used internally by `/flow`):

- `arquiteto` — same persona as the command, as an isolated opinion.
- `analyst` — same persona as the command, as an isolated opinion.

Skills (trigger on their own based on context, no command needed):

- `test-failure-triage` — protocol for classifying a failing existing test (real regression / rule changed / flaky).
- `code-review` — review checklist (general + layers + tests), with an optional .NET example.
- `conventional-commit` — commit message convention (`feat`/`fix`/etc.).

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

## Versioning

- One tag per improvement (e.g. `v0.2.0` when a new skill or flow adjustment is added) — no scheduled releases, no batching unrelated changes under one tag.
- `CHANGELOG.md` records what changed in each version, following [Keep a Changelog](https://keepachangelog.com/).
- The `version` in `.claude-plugin/marketplace.json` and in each `plugin.json` tracks the latest tag that touched that plugin.

## Contributing

Before adding something new, read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — it explains when something should be a command, an agent or a skill. All content in this repository is written in English.
