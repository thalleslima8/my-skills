---
name: api
description: Exploratory HTTP client, Postman/Insomnia-style, driven by Claude — build and send a request to the project's local API, chain calls by capturing response fields, save requests to reuse, and start/restart the local dev server when needed. Use when the user asks to test or hit an endpoint, send a request to the local API, re-run or save a request ("testar", "testa esse endpoint", "bater na rota", "chamar a API local", "guardar essa request", "guarda essa chamada"). NOT /qa — no test cases, no pass/fail verdict, no report; this is a step-by-step exploratory lab, one call at a time.
---

# /api — exploratory HTTP client for the project's local API

A stdlib-only Python runner that plays the role of Insomnia/Postman: it builds the request, authenticates, sends it, shows the result and can save the call for reuse. Project state lives in `.claude/api/` of the project it runs in. It complements `/qa` (suites, pass/fail, reports) without overlapping it: here there is no "test case" and no formal report — the user says "test this", "hit that route", "save this call", one step at a time. It never fixes code (that is `/spike`).

## Running the runner

Every call is:

```bash
python3 "<base directory of this skill>/scripts/api.py" <command> ...
```

Claude Code prints "Base directory for this skill: …" when the skill loads — use that absolute path, so the call works from any directory. Below, `api.py` stands for that full command.

- **Interpreter:** try `python3`, then `python`, then `py -3` (`--version` is enough to check) and use the first that works for every call. Windows machines often have none. The API normally runs inside a Dev Container/WSL/VM — run the runner in that environment, where Claude Code usually is too. If there is no Python anywhere, say so and ask; do not install one on your own.
- **Project root:** `--root DIR` (before or after the command) > `$CLAUDE_PROJECT_DIR` > the nearest directory above the current one that contains `.claude/` or `.git`. Pass `--root` when the shell is not inside the project.
- **Errors:** usage/environment problems print `ERRO: ...` on stderr and exit with code 2. An HTTP 4xx/5xx is **not** an error of the tool — it is printed like any other response.

## Typical flow

0. **First time in a project — no `.claude/api/config.json`:** run `api.py init`. It creates `.claude/api/` with `config.json` and `env.local.json` (mode 600), adds `.claude/api/env.local.json` and `.claude/api/.last/` to `.gitignore` (idempotent), and proposes a `host` block from the detected stack (`host.json` → Azure Functions `func host start`; a web `*.csproj` → `dotnet run`; `package.json` with a `dev` script → `npm run dev`; otherwise none). **Show the user what it proposed** (`baseUrl`, `defaultAuth`, `auth`, `host`) and adjust `config.json` with them before relying on it. It never overwrites an existing `config.json` without `--force`, and an older `.claude/api/` (with `requests/` and `env.local.json`) is left as is.

1. **First call of the session / suspected stale host** (only if `host` is configured):
   ```bash
   api.py host status
   ```
   On "DOWN", or the warning that source files are newer than the host start, run `api.py host restart`. It stops the previous process (the PID saved in `.last/host.json`, plus `host.processPatterns` as backup), starts `host.start`, polls `host.healthUrl` until it answers (`startTimeoutSec`) and, if the process dies while starting, prints the last log lines. Never assume "it must already be up". `api.py host logs -n 50` shows the log.

2. **No credentials/tenant/ids for local dev yet, or the local database was reset** (only if `seed` is configured):
   ```bash
   api.py seed            # add --rotate to ask the hook for a fresh credential
   ```
   Runs the project's own seed command and merges what it prints into `env.local.json`. See "Seed hook" below.

3. **See what is already there:**
   ```bash
   api.py list            # saved requests
   api.py env show        # baseUrl + variables (secrets masked)
   ```

4. **Hit a route ad hoc:**
   ```bash
   api.py send GET /v1/items --query count=5
   api.py send POST /v1/items/{{itemId}}/notes --body '{"text":"hello"}' --header 'X-Trace: 1'
   api.py send POST /v1/items --body @payload.json --timeout 120
   ```
   `--auth <name>` picks an entry of the `auth` map in `config.json` (default: `defaultAuth`); `--auth none` sends no credentials. The credential is read from the variable that entry names (e.g. `env set bearerToken=<jwt>`). Paths are relative to `baseUrl`.

5. **When the user asks to keep the call** ("guarda essa request", "deixa pronto pra eu rodar de novo"): repeat the `send` with `--save name/of/request` (subfolders allowed) — it writes `.claude/api/requests/name/of/request.json` with **no secrets, only `{{variables}}`**, and warns if a header/query/body field with a sensitive name holds a fixed value. Replay with:
   ```bash
   api.py run group/request
   api.py run group/request --var itemId=<other-id>
   ```

6. **Chain a flow (create → fetch)** by capturing a response field for the next call: `--capture var=$.path.in.response` on `send`, or `"capture": {"itemId": "$.id"}` in the saved JSON. The value goes to `env.local.json` and is available as `{{itemId}}` in the next request. It only captures from a 2xx response with a JSON body — on an error it warns and leaves the variable untouched. Paths are a mini-JSONPath: `$.a.b[0].c`, `$[0].id`.

7. **After every call** the runner prints method + URL, status, time in ms, content-type, `Retry-After` when present, and the body (JSON indented, truncated at 4000 chars — `--full` disables that). It writes `.claude/api/.last/<name>.json` and appends to `.claude/api/.last/history.jsonl`. Review without repeating the call: `api.py history -n 20`. Redirects are shown, **not followed**.

## `config.json` (versioned, no secrets)

```json
{
  "baseUrl": "http://localhost:7071/api",
  "localHosts": ["localhost", "127.0.0.1", "::1"],
  "defaultAuth": "apikey",
  "auth": {
    "apikey": { "var": "apiKey", "header": "Authorization", "format": "ApiKey {value}" },
    "bearer": { "var": "bearerToken", "header": "Authorization", "format": "Bearer {value}" },
    "none": null
  },
  "host": {
    "cwd": "src/MyApp.Functions",
    "start": ["func", "host", "start", "--port", "7071"],
    "healthUrl": "http://localhost:7071/",
    "processPatterns": ["func host start", "MyApp.Functions.dll"],
    "sourceGlobs": ["src/**/*.cs"],
    "sourceIgnore": ["**/obj/**", "**/bin/**"],
    "startTimeoutSec": 180
  },
  "seed": { "command": ["python3", ".claude/api/seed.py"] }
}
```

- `baseUrl` — every request path is appended to it. Include any route prefix here (a stack that serves under `/api` puts `/api` in `baseUrl` and the request paths start at `/v1/...`). `env.local.json` may carry its own `baseUrl` as a per-machine override; `env set baseUrl=...` writes there.
- `localHosts` — hosts `send`/`run` accept without `--allow-remote` (default `localhost`, `127.0.0.1`, `::1`).
- `auth` — name → `{var, header, format}`; the header value is `format` with `{value}` replaced by the variable `var`. `none` (or `null`) sends nothing. `defaultAuth` applies when a request does not name one.
- `host` (optional) — `cwd` (relative to the project root), `start` (argv, no shell), `healthUrl` (default: `baseUrl`), `processPatterns` (for `pgrep -f`; keep them specific to this project, they can kill matching processes), `sourceGlobs`/`sourceIgnore` (relative to the root; with no `sourceGlobs`, `host status` never warns that the process is outdated), `startTimeoutSec` (default 180).
- `seed` (optional) — the hook, below.

Without `host` or `seed`, those commands answer "not configured in this project — see `init`".

## Seed hook

`seed.command` is an argv the **project** provides. `api.py seed` runs it from the project root (adding `--rotate` if asked) and expects a JSON object on stdout: `{"baseUrl"?: "...", "vars": {"name": "value", ...}}`. The runner merges it into `env.local.json` and prints the result masked. Contract:

- the command must refuse a non-local target on its own; the runner also refuses to run it when `baseUrl` is not local, and refuses a non-local `baseUrl` in its output;
- progress messages go to stderr — stdout is only the JSON;
- exit code ≠ 0 fails `seed` and shows the command's stderr.

If `seed` is not configured and the user needs local dev data, say how to add the hook; do not write database access into this skill.

## Variable syntax (`{{...}}`)

- `{{name}}` — from `env.local.json` or `--var name=value` at `send`/`run` time. If it is missing the runner **refuses and names exactly which variable is missing** — it never sends the literal placeholder.
- `{{name|default}}` — uses `default` when `name` is not defined (e.g. `{{count|20}}`).
- `{{$guid}}` / `{{$now}}` — a new GUID / UTC ISO-8601 timestamp on every execution.
- In a **query** value (never in path or body), a lone `{{name}}` with no value available means "optional parameter, omit it" instead of an error.

## Guardrails (do not work around them)

- **Local only by default.** `send`/`run` refuse a `baseUrl` whose host is not in `localHosts`. Only when the user explicitly and unambiguously authorizes a remote environment **in that same turn**, pass `--allow-remote` and point `baseUrl` there with `env set baseUrl=...` — then set it back to the local URL afterwards. Never do this on your own. `seed` never runs against a remote target.
- **Secrets stay out of the repo and out of your reply.** `env.local.json` (mode 600) and `.last/` are gitignored. Any key matching `secret|token|password|api-key|authorization` is masked (`ABCD…(64 chars)`) in `env show`, `history` and everything written to `.last/`, including query-string parameters of the URL. Never paste a full ApiKey/token into your answer to the user — say it "is set" instead. Never put a real secret in a saved request; use a `{{variable}}`.
- **Do not commit** anything for the user, and do not edit `env.local.json` by hand — use `env set`.

## Investigating a failure (4xx/5xx)

First read the project's `CLAUDE.md` section **"API"** for what its status codes and auth rules mean. If that section does not exist, ask the user instead of assuming. Then read the handler/middleware behind the route before concluding anything. Generic starting points:

- **Connection error / timeout** → is the host up (`host status`), is `baseUrl` right, does the call need a bigger `--timeout`?
- **400 / 422** → the payload or query does not match the validation; compare with the handler's contract.
- **401** → no valid credentials: the auth entry, the variable behind it (confirm it is set — do not print it), expiry or revocation.
- **403** → authenticated but not allowed for this route/role.
- **404** → wrong route or prefix (is a prefix duplicated between `baseUrl` and the path?), or a resource the caller is not allowed to know exists.
- **409** → conflict with the resource's state or a concurrent change.
- **429** → rate limit; the runner already prints `Retry-After`.
- **5xx** → `host logs`, then the handler.

If the cause is not obvious, follow the normal investigation/bug-fix flow of `/spike` — this skill does not fix code, it only exercises the API.

## Adding new reference requests

`.claude/api/requests/` is the catalogue of ready-to-reuse calls — organize it by resource (`items/`, `orders/`, …), one file per call. After creating one with `--save`, review the generated JSON before calling it done: confirm no fixed value should have been a `{{variable}}` (ids from another environment, for example) — the runner saves exactly what you typed, it does not infer that.

```json
{
  "name": "Search items (optional filters)",
  "method": "GET",
  "path": "/v1/items",
  "query": { "q": "{{q}}", "page": "1", "count": "{{count|20}}" },
  "capture": { "firstItemId": "$[0].id" }
}
```

## Command reference

| Command | What it does |
|---|---|
| `init [--force]` | Create `.claude/api/` (config + env), update `.gitignore`, propose `host` |
| `send METHOD PATH [--body JSON\|@file] [--query k=v]... [--header Name:value]... [--auth name] [--capture var=$.a.b[0]]... [--save name] [--var k=v]... [--full] [--timeout SEC] [--allow-remote]` | Ad-hoc request |
| `run <name\|path.json> [--var k=v]... [--full] [--timeout SEC] [--allow-remote]` | Saved request |
| `list` / `show <name>` | Saved requests |
| `env show` / `env set k=v...` | Variables (`baseUrl` is special) |
| `history [-n N]` | Recent calls |
| `host status\|restart\|logs [-n N]` | Local dev server |
| `seed [--rotate]` | Project seed hook |

`--timeout` defaults to 60 seconds.

## On disk

```
.claude/api/
  config.json        versioned, no secrets
  env.local.json     secrets, gitignored: {"baseUrl"?: "...", "vars": {...}}
  requests/**/*.json versioned
  .last/             gitignored: history.jsonl, host.json, host.log, <name>.json
```

`host restart` is POSIX-first (PID + process group + `pgrep`). On Windows it falls back to `taskkill` on the saved PID only, and `processPatterns` are not applied — prefer running everything inside the container/WSL where the API runs.
