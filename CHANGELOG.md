# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
