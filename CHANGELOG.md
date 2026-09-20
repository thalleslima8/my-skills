# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

[0.2.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/thalleslima8/my-skills/releases/tag/v0.1.0
