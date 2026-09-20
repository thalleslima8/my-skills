---
name: migrate-legacy-claude
description: Use when the user asks to migrate an existing project (one that already has its own `.claude/` folder with local commands and rules) to the my-skills plugins — e.g. "migrate this project to my-skills", "replace the local commands with the my-skills ones", "adapt this old .claude/ to the new stack". Do NOT use on a new/empty project (that is the ai-starter-kit's job) nor for routine development inside an already-migrated project.
---

# Migrate a legacy `.claude/` to the my-skills plugins

A legacy project carries its own `.claude/commands/` — copies of the workflow (analyst, architect, spike, QA…) with project rules mixed into the process text. The goal is to replace those copies with the `workflow` plugin **without losing anything that is specific to the project**: that knowledge moves to the project's `CLAUDE.md`, which is where the plugin's commands read it from.

## Ground rules

1. **Never remove a command until every project-specific piece of information inside it lives somewhere else** — the project's `CLAUDE.md`, or a preserved category C command.
2. **When in doubt, keep.** Unsure whether a passage is generic process or a project rule → treat it as a project rule (duplicating it in `CLAUDE.md` is cheap, losing it is not). Unsure between A and B → B. Unsure whether an equivalent exists → C.
3. **Dry-run first.** Steps 1–3 are read-only. Show the report and get the user's explicit confirmation before writing or deleting anything.
4. **Never delete without a backup**, and never touch category C commands, `settings.local.json`, hooks, or local agents/skills.
5. **Cannot classify something with confidence → stop before step 4 and ask.** Do not decide alone.
6. Do not commit anything. Leave that to the user.

## Step 1 — Inventory (read-only)

Do not assume file names — use Glob/Read on the real project.

1. Glob every `.claude/` directory in the project (skip `node_modules`, `.git`, build output). Monorepos and legacy setups often have more than one (e.g. a canonical copy plus a mirror in a subfolder). Each one is migrated separately; if two contain a command with the same name, diff them — if they diverge, that is an ambiguity to ask about.
2. In each, list what exists: `commands/`, `agents/`, `skills/`, `settings.json`, `settings.local.json`, `hooks/`, and any other file you find.
3. **Read every local command completely** (all of it, in chunks if needed — project rules are often buried mid-file).
4. Read the project's `CLAUDE.md` if it exists (also `.claude/CLAUDE.md` / `CLAUDE.local.md` if present); note its existing sections and language.
5. Read `settings.json`. Note which hooks or permission entries reference files or commands inside `.claude/`.
6. Read the plugin's own commands to compare against. They sit at `../../commands/` relative to this skill's base directory (shown when the skill loads); the agents are at `../../agents/`. If that path is not readable, fetch `plugins/workflow/commands/` from `thalleslima8/my-skills` on GitHub. Use the actual directory listing, not a remembered list (today: analyst, arquiteto, flow, spike, qa, infra).

## Step 2 — Match each command to the plugin

Compare **responsibility**, never file name or `description` alone. A project may have renamed `/spike` to `/dev`, or `/qa` to `/test`. Read the local command against each plugin command body.

Split each local command into passages and label every passage:
- **Process** — would read the same in any product, *and* you found the counterpart in the plugin command. Verify by locating it; do not assume it is covered.
- **Specific** — tied to this project: entity/domain names, paths, layer names, tools/frameworks/versions, commands to run, URLs/ports, credentials or test accounts, limits/thresholds, cost policies, naming or commit conventions, security checklist items, business or regulatory rules. A generic-looking passage that *differs* from the plugin's (other steps, order, report format, stricter rule) is also specific — it is a deliberate customization.

Then classify the command:

| Category | Test | Outcome |
|---|---|---|
| **A — Direct equivalent** | Same responsibility as a plugin command, no specific passages | Replaced |
| **B — Partial equivalent** | Same responsibility, but with specific passages mixed in | Replaced, after extracting the specific parts (step 3) |
| **C — No equivalent** | Automation unique to the project (e.g. a staging-deploy command, a proprietary API integration) | **Never removed** — stays as is |

Hybrids: a local command that covers more than one plugin responsibility, or an equivalent part plus genuinely unique automation in the same file, must not be guessed at. List it as ambiguous and ask (keep as C, or split it).

Local agents and skills are not removed. If one duplicates a plugin agent or skill, list it under manual action pending.

## Step 3 — Plan the extraction

For every **B** command, take each specific passage — verbatim. Keep identifiers, paths, commands, numbers and the project's own language; do not paraphrase or translate. Skip pure process text only after you located its counterpart in the plugin (Step 2). Decide the destination of each passage:

| What it is | Where it goes |
|---|---|
| Security rules, migration conventions, layers, stack, entity naming | Project `CLAUDE.md`, in the section the plugin reads it from: **Stack e camadas específicas do projeto** (security, migrations and layers as subsections, as the template's own comment prescribes) |
| Test stack, mocks/fixtures, test patterns | **Testes** (subsection under the stack section if the file has none) |
| Epic folders, states, ID/decision conventions | **Task management** |
| Commit format and rules | **Convenções de commit** |
| Code naming and formatting | **Convenções de código** |
| Test credentials, environment URLs, page map (typical in a local `qa.md`) | A QA section of `CLAUDE.md`, labelled with the placeholder names the plugin's `qa.md` expects to read |

Section names above are the headings of the ai-starter-kit template (`thalleslima8/ai-starter-kit`, `CLAUDE.md`). If the project already has a `CLAUDE.md`, use its own headings and language where they exist, and add the missing ones.

**QA values.** The plugin's `qa.md` reads its values from `CLAUDE.md` under these names: `LOCAL_URL`, `PRODUCTION_URL`, `TEST_LOGIN`, `TEST_PASSWORD`, `LOGIN_ROUTE`, `DB_ENGINE`, `ProductDb`, plus the backend/frontend process names, start commands and local URLs, and the "App map" (Main pages table `Page | Route | Authentication`, Main flows). Write each extracted value labelled with the name it fills, e.g. `LOCAL_URL: http://localhost:5173`, and reproduce the app-map table format. Read the plugin's `qa.md` to get the current list.

**Secrets.** `CLAUDE.md` is committed. Copy only local/test-environment credentials that were already sitting in a tracked command file. Anything that looks like a production secret, token or connection string with a password is **not** copied — reference the environment variable name instead and list it under manual action pending (it may also need rotation, since it is in git history).

**No `CLAUDE.md` yet.** Create it from the ai-starter-kit template. Fetch it with `gh api repos/thalleslima8/ai-starter-kit/contents/CLAUDE.md --jq .content | base64 -d` (or the raw file); keep its headings verbatim, replace the placeholders and instructional comments with the extracted content, and leave `{preencher}` where you have nothing real to write — never invent content. If the template cannot be fetched, ask the user; do not reconstruct it from memory.

**Existing `CLAUDE.md`.** Add under the matching heading. Do not rewrite, reorder or deduplicate what is there. If the same rule is already present with the same content, record "already covered at <section>" instead of duplicating. If it is present with a *different* value or wording, that is a conflict — ask.

Build the extraction table: `Source (file › passage)` · `Kind` · `Destination (CLAUDE.md § section)` · `Action (add / already covered at… / conflict)`.

## Checkpoint — dry-run report and confirmation

Before touching any file, present, in this order:
1. The inventory (per `.claude/`: what exists).
2. The classification table: each local command → A/B/C, the plugin command it maps to, and which passages were judged process vs. specific.
3. The extraction table.
4. Exactly which command files will be removed, which stay (C), the backup path, and the `settings.json` change as a diff.
5. Every ambiguity, each as a concrete question.

Then wait for explicit confirmation of *that* plan. If the answers change the plan, re-show the changed parts. If there is no user to answer (non-interactive run), stop here and change nothing.

## Step 4 — Replace (only after confirmation)

1. **Backup.** Recursively copy each `.claude/` being migrated, everything included (`settings.local.json`, hooks), to `.claude.bak-<YYYY-MM-DD>/` next to it. Never overwrite an existing backup — add a `-2` suffix. If `CLAUDE.md` will be modified, copy its original into the backup too. Compare the file lists of original and backup before going on. Do not stage or commit the backup.
2. **Write the extraction** into `CLAUDE.md`, then **verify it**: re-read the file and tick every row of the extraction table. A row not found in `CLAUDE.md` (or its "already covered" location) blocks the removal — fix it first.
3. **Merge `.claude/settings.json`** — never overwrite:
   ```json
   {
     "extraKnownMarketplaces": {
       "my-skills": { "source": { "source": "github", "repo": "thalleslima8/my-skills" } }
     },
     "enabledPlugins": { "workflow@my-skills": true }
   }
   ```
   Parse the existing file and add only these keys; keep `permissions` (`allow`/`deny`/`ask`), `hooks`, `env` and everything else as is, plus any other marketplaces/plugins already listed. If `my-skills` is already declared with a different source, ask. If the file is not plain JSON (comments, trailing commas), stop and ask rather than rewrite it. If it does not exist, create it with just these keys. If the project is .NET/EF Core (`.sln`/`.csproj`, EF migrations), also add `"dotnet@my-skills": true`. Preserve the file's indentation and confirm the result parses. Never edit `settings.local.json`.
4. **Remove** exactly the A and B command files listed in the confirmed plan. Leave every C file byte-identical, and do not delete anything else — files a removed command used (scripts, templates) are only listed as possibly orphaned.
5. **Check dangling references.** Grep the remaining `.claude/` files, `CLAUDE.md`, docs, hooks and settings for the removed command names (renamed ones especially, e.g. `/dev` → `/spike`). Fix the ones in files you already edit; report the rest.

## Step 5 — Final report (mandatory)

Deliver this before considering the migration done. The dry-run at the checkpoint uses the same headings, written as "proposed".

```
## Migration to my-skills — <project name>

### Commands replaced (A/B)
- analyst.md → direct equivalent, no project-specific content lost
- dev.md (now /spike) → partial: security checklist and migration command moved to CLAUDE.md § Stack e camadas específicas do projeto

### Commands kept (C)
- deploy-staging.md → project's own automation, no equivalent

### What went into CLAUDE.md
[each extracted item and the section it went to]

### Backup
.claude.bak-<date>/ holds the complete original state

### Manual action pending
[anything not confidently classified, conflicts, possibly orphaned files, dangling references,
secrets not copied, local agents/skills that duplicate plugin ones, whether to commit or
gitignore the backup, and: restart Claude Code in the project so the marketplace and plugin
load, then confirm the plugin commands (e.g. /spike) resolve]
```
