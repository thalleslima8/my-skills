# Contributing

This repository distributes three kinds of Claude Code artifact: **command**, **agent** and **skill**. They solve different problems — picking the wrong kind is the most common reason an artifact "exists but nobody uses it" or fires at the wrong time.

All content in this repository (docs, prompts, frontmatter, manifests) is written in English.

## Command — when the user explicitly chooses to enter a working mode

Use `commands/` when:
- The person needs to **consciously decide** to enter a session with a specific identity and rule set (e.g. "now I want architect mode").
- The behavior involves **controlling a whole session** — initialization, modes, internal state accumulated over many turns, "session is getting heavy" warnings.
- It makes sense for the person to type `/command-name` and see it as the start of a workflow, not as an implementation detail.

Examples in this repository: `/spike` (a whole development session, with modes), `/flow` (a mediation session with state accumulated across discussed points).

## Agent — when another process (not a person) needs the same persona in isolation

Use `agents/` when:
- The same identity/instructions as a command need to be **called programmatically**, via `Agent(subagent_type: "...")`, usually from another command.
- Each call is **isolated** — the agent does not need to remember earlier conversation, only the prompt it received.
- There is no need for a "session" (no multi-turn initialization, no accumulated context control) — the agent answers and returns its opinion.

Example in this repository: `arquiteto` and `analyst` exist as agents because `/flow` needs an isolated opinion from each, without one seeing the other's answer. If someone wants to talk directly to the architect in a long session, the `/arquiteto` command still exists for that — a command and an agent can coexist and reuse the same persona.

**Rule of thumb:** if the question is "does another agent/command need to call this, with no human in the middle?", it is an agent. If the question is "will a human type this and converse for several turns?", it is a command.

## Skill — when the behavior should fire on its own, based on context

Use `skills/` when:
- The logic is a **reusable procedure** that should apply whenever the context calls for it, **regardless of which command or agent is active**.
- It makes no sense for the person to remember to invoke it explicitly — if they forget, the correct behavior should still happen.
- The trigger can be described in one clear `description` sentence that lets Claude decide on its own when to apply it.

Examples in this repository: `test-failure-triage` (should fire every time an existing test fails, not only when someone remembers to ask), `code-review` (the review checklist should apply both inside `/spike` and in any other review context), `conventional-commit` (a message convention that should apply to any generated commit, not only inside one specific flow), `ef-migrations` (a rule that only applies to .NET/EF Core projects — which is why it lives in a separate plugin, not inside `workflow`).

**Sign that something should be a skill instead of staying inside a command:** the logic is written inside a command's `.md`, but would be equally valid if triggered from anywhere else in the project. In that case, extract it to `skills/` and let the command just reference the skill by name.

## Where to put a new stack-specific skill

If a skill only makes sense for a specific stack/framework (e.g. a rule that only exists in Rails projects, or in projects with Terraform), **do not put it in the `workflow` plugin** — create (or use) a plugin dedicated to that stack, like this repository's `dotnet` plugin. This keeps `workflow` installable in any project, regardless of stack.

## Third-party content

When adapting a skill, command or agent from another project, check its license first. Keep the original license file next to the adapted artifact, name the upstream repository and version in the artifact's frontmatter, and list the modifications in `CHANGELOG.md`. Example: `plugins/writing/skills/humanizer/`.

## Checklist before opening a change

- [ ] The new/changed artifact does not mention a product name, company name or specific stack outside the matching stack plugin
- [ ] Every convention that varies per project is written as "as defined in the project's CLAUDE.md" — never hardcoded
- [ ] Any reference to a structural convention (e.g. where epics live) is marked "if the project uses that convention"
- [ ] The skill/agent `description` is specific enough to fire / be called at the right time
- [ ] Everything is written in English
- [ ] Third-party content keeps its license and attribution
- [ ] `CHANGELOG.md` is updated
