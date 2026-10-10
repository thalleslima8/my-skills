# Contributing

This repository distributes three kinds of Claude Code artifact: **command**, **agent** and **skill**. They solve different problems — picking the wrong kind is the most common reason an artifact "exists but nobody uses it" or fires at the wrong time.

All content in this repository (docs, prompts, frontmatter, manifests) is written in English.

## Command — when the user explicitly chooses to enter a working mode

Use `commands/` when:
- The person needs to **consciously decide** to enter a session with a specific identity and rule set (e.g. "now I want architect mode").
- The behavior involves **controlling a whole session** — initialization, modes, internal state accumulated over many turns, "session is getting heavy" warnings.
- It makes sense for the person to type `/command-name` and see it as the start of a workflow, not as an implementation detail.

Examples in this repository: `/spike` (a whole development session, with modes), `/flow` (a mediation session with state accumulated across discussed points, or, on an explicit request, a run that implements the epics up to a single pull request).

## Agent — when another process (not a person) needs the same persona in isolation

Use `agents/` when:
- The same identity/instructions as a command need to be **called programmatically**, via `Agent(subagent_type: "...")`, usually from another command.
- Each call is **isolated** — the agent does not need to remember earlier conversation, only the prompt it received.
- There is no need for a "session" (no multi-turn initialization, no accumulated context control) — the agent answers and returns its opinion.

Example in this repository: `arquiteto` and `analyst` exist as agents because `/flow` needs an isolated opinion from each, without one seeing the other's answer. If someone wants to talk directly to the architect in a long session, the `/arquiteto` command still exists for that — a command and an agent can coexist and reuse the same persona.

`spike` is an agent for the same reason: `/flow`'s execution mode calls it with no human in the middle. It is not a copy of the `/spike` command: the agent holds only what an implementer needs when nobody is there to answer (its input blocks, the rule register, the definition of done, the `DONE` / `BLOCKED` / `HANDOFF` blocks), and the command holds the session a person converses with. Rules the two share are stated in both, in each one's own terms; when you change one, check the other.

An agent's frontmatter also sets what a call costs. Give it the `model` its work needs and only the `tools` it uses: an agent that only gives an opinion does not need the session's largest model nor tools that write.

**Rule of thumb:** if the question is "does another agent/command need to call this, with no human in the middle?", it is an agent. If the question is "will a human type this and converse for several turns?", it is a command.

## Skill — when the behavior should fire on its own, based on context

Use `skills/` when:
- The logic is a **reusable procedure** that should apply whenever the context calls for it, **regardless of which command or agent is active**.
- It makes no sense for the person to remember to invoke it explicitly — if they forget, the correct behavior should still happen.
- The trigger can be described in one clear `description` sentence that lets Claude decide on its own when to apply it.

Examples in this repository: `test-failure-triage` (should fire every time an existing test fails, not only when someone remembers to ask), `code-review` (the standards-driven review should apply both inside `/spike` and in any other review context), `conventional-commit` (a message convention that should apply to any generated commit, not only inside one specific flow), `ef-migrations` (a rule that only applies to .NET/EF Core projects — which is why it lives in a separate plugin, not inside `workflow`).

**Sign that something should be a skill instead of staying inside a command:** the logic is written inside a command's `.md`, but would be equally valid if triggered from anywhere else in the project. In that case, extract it to `skills/` and let the command just reference the skill by name.

## Where to put a new stack-specific skill

If a skill only makes sense for a specific stack/framework (e.g. a rule that only exists in Rails projects, or in projects with Terraform), **do not put it in the `workflow` plugin** — create (or use) a plugin dedicated to that stack, like this repository's `dotnet` plugin. This keeps `workflow` installable in any project, regardless of stack.

## Skills that ship code

A skill may carry a script it calls (e.g. `plugins/workflow/skills/api/scripts/api.py`). Keep it standard-library only, keep everything project-specific in the project's own configuration files, and ship its tests next to it (`tests/`, stdlib `unittest`). Run them from the repository root, in an environment that has Python 3:

```
python3 -m unittest discover -s plugins/workflow/skills/api/tests -v
```

Say in the change description if you could not run them — do not report them as passing.

## Keeping a command light

A command's whole file is loaded when the user types it and stays in the session's context for every later step. When a command has a mode that most sessions never enter, move that mode's rules to a skill the command loads on demand, and say in the skill's `description` that only that command starts it. Example: `/flow` holds the mediation rules, and its execution mode lives in the `flow-execution` skill.

## Measuring a workflow change

A change to `/flow`, the `spike` agent or the review gate is meant to cost fewer rounds or fewer tokens, so measure it. `scripts/usage-report.ps1` reads the local transcripts of a project where the plugin runs (`~/.claude/projects/`):

```
pwsh scripts/usage-report.ps1 -Project <part of the project folder name> -Days 7
pwsh scripts/usage-report.ps1 -Project <name> -Session <id prefix> -Detail
```

Compare, for a run before and a run after the change:

- **Rounds per epic** — `FullReviews` should be 1 per epic, with the rest as `DeltaReviews`; `SpikeCalls` plus the `SendMessage` count in `MainTools` shows how many times the implementation went back.
- **Context** — `SpikeMaxCtxK` (a slice that fills the window loses details) and `MainMaxCtxK` (every step of a long session re-reads its whole history).
- **Where the input tokens went** — "Totals by kind". The numbers are input-side: transcripts under-report output tokens, so `OutK` is a floor.
- **Comments on the pull request** — not in the transcripts: count the review comments the run got. That is what the definition of done and the polish round are there to reduce.

The script needs PowerShell 7 and reads only your own machine's transcripts.

## Third-party content

When adapting a skill, command or agent from another project, check its license first. Keep the original license file next to the adapted artifact, name the upstream repository and version in the artifact's frontmatter, and list the modifications in `CHANGELOG.md`. Example: `plugins/writing/skills/humanizer/`.

## Checklist before opening a change

- [ ] The new/changed artifact does not mention a product name, company name or specific stack outside the matching stack plugin
- [ ] Every convention that varies per project is written as "as defined in the project's CLAUDE.md" — never hardcoded
- [ ] Any reference to a structural convention (e.g. where epics live) is marked "if the project uses that convention"
- [ ] The skill/agent `description` is specific enough to fire / be called at the right time
- [ ] An agent declares its `model`, and its `tools` when it does not need all of them
- [ ] A rule shared by the `/spike` command and the `spike` agent was changed in both
- [ ] Everything is written in English
- [ ] Third-party content keeps its license and attribution
- [ ] `CHANGELOG.md` is updated
