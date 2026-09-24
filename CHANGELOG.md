# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
