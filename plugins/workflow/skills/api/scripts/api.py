#!/usr/bin/env python3
"""Runner of the `api` skill: an exploratory "Postman/Insomnia" driven by Claude.

Standard library only. Project state lives in <project root>/.claude/api/:

  config.json       versioned, no secrets: baseUrl, auth map, host, seed hook
  env.local.json    secrets, gitignored: {"baseUrl"?: "...", "vars": {...}}
  requests/**.json  versioned saved requests (only {{variables}}, never secrets)
  .last/            gitignored: history.jsonl, host.json, host.log, <name>.json

The project root is resolved by: --root > $CLAUDE_PROJECT_DIR > walking up from the
current directory until a `.claude/` or `.git` entry is found.

Usage: python3 api.py [--root DIR] <command> ...   (see --help)
"""
import argparse
import fnmatch
import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SENSITIVE_KEY = re.compile(r"secret|token|password|api[-_]?key|authorization", re.I)  # `api-key` also covers the X-Api-Key header
VAR_PATTERN = re.compile(r"\{\{\s*([\w$.\-]+)\s*(?:\|([^}]*))?\}\}")

ROOT_MARKERS = (".claude", ".git")
DEFAULT_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
DEFAULT_TIMEOUT = 60.0
DEFAULT_START_TIMEOUT = 180.0
SEED_TIMEOUT = 300
BODY_LIMIT = 4000
GITIGNORE_ENTRIES = (".claude/api/env.local.json", ".claude/api/.last/")
IS_WINDOWS = os.name == "nt"


class ToolError(Exception):
    """Usage/environment error (not an HTTP response)."""


# --------------------------------------------------------------- project layout

class Project:
    """Where the skill keeps its state for one project."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.api_dir = self.root / ".claude" / "api"
        self.requests_dir = self.api_dir / "requests"
        self.config_file = self.api_dir / "config.json"
        self.env_file = self.api_dir / "env.local.json"
        self.last_dir = self.api_dir / ".last"

    def rel(self, path):
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)


def find_project_root(start, markers=ROOT_MARKERS):
    """Nearest directory at or above `start` that contains one of `markers`."""
    start = Path(start).resolve()
    try:
        home = Path.home().resolve()
    except (RuntimeError, KeyError, OSError):
        home = None
    for directory in (start, *start.parents):
        for marker in markers:
            if marker == ".claude" and directory == home:
                continue  # ~/.claude is user-level configuration, not a project
            if (directory / marker).exists():
                return directory
    return None


def resolve_root(explicit=None, environ=None, cwd=None):
    """--root > CLAUDE_PROJECT_DIR > walk up from the cwd to `.claude/` or `.git`."""
    environ = os.environ if environ is None else environ
    chosen = explicit or environ.get("CLAUDE_PROJECT_DIR")
    if chosen:
        root = Path(chosen).resolve()
        if not root.is_dir():
            raise ToolError(f"Project root does not exist: {root}")
        return root
    found = find_project_root(cwd or Path.cwd())
    if found is None:
        raise ToolError(
            "Could not find the project root (no .claude/ or .git above the current directory). "
            "Pass --root DIR or set CLAUDE_PROJECT_DIR.")
    return found


# ------------------------------------------------------------------- file helpers

def read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ToolError(f"{what} not found: {path}")
    except ValueError as error:
        raise ToolError(f"{what} is not valid JSON ({path}): {error}")


def write_text(path, text, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not private:
        path.write_text(text, encoding="utf-8")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    try:
        os.chmod(path, 0o600)  # the mode passed to os.open only applies to new files
    except OSError:
        pass


def dump_json(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------ config and env

def load_config(project):
    if not project.config_file.exists():
        return {}
    config = read_json(project.config_file, "config.json")
    if not isinstance(config, dict):
        raise ToolError("config.json must be a JSON object.")
    return config


def load_env(project):
    if not project.env_file.exists():
        return {"vars": {}}
    env = read_json(project.env_file, "env.local.json")
    if not isinstance(env, dict) or not isinstance(env.setdefault("vars", {}), dict):
        raise ToolError('env.local.json must look like {"baseUrl": "...", "vars": {...}}.')
    return env


def save_env(project, env):
    write_text(project.env_file, dump_json(env), private=True)


def effective_base_url(env, config):
    """env.local.json `baseUrl` (per-machine override) wins over config.json."""
    base = env.get("baseUrl") or config.get("baseUrl")
    if not base:
        raise ToolError(
            "No baseUrl. Set it in .claude/api/config.json or with `env set baseUrl=...` "
            "(run `init` if this project has no config yet).")
    return str(base).rstrip("/")


def local_hosts(config):
    hosts = config.get("localHosts")
    if hosts is None:
        return DEFAULT_LOCAL_HOSTS
    if not isinstance(hosts, list) or not all(isinstance(h, str) for h in hosts):
        raise ToolError("localHosts in config.json must be a list of host names.")
    return tuple(hosts)


def auth_var_names(config):
    auth = config.get("auth")
    if not isinstance(auth, dict):
        return set()
    return {entry["var"] for entry in auth.values() if isinstance(entry, dict) and "var" in entry}


def seed_command(config):
    seed = config.get("seed")
    command = seed.get("command") if isinstance(seed, dict) else None
    if isinstance(command, list) and command and all(isinstance(part, str) for part in command):
        return command
    return None


# ------------------------------------------------------------------------ secrets

def is_sensitive(key, extra=()):
    return bool(SENSITIVE_KEY.search(key)) or key in extra


def mask(key, value, extra=()):
    if is_sensitive(key, extra) and isinstance(value, str) and value:
        return value[:4] + "…(" + str(len(value)) + " chars)"
    return value


def redact(node):
    """Copy with sensitive fields masked — used for whatever is written to disk (.last/history)."""
    if isinstance(node, dict):
        return {k: (mask(k, v) if isinstance(v, str) else redact(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [redact(item) for item in node]
    return node


def redact_url(url):
    """The URL with the value of every sensitive query parameter (?token=...) masked."""
    parts = urllib.parse.urlsplit(url)
    if not parts.query:
        return url
    chunks = []
    for chunk in parts.query.split("&"):
        key, sep, value = chunk.partition("=")
        name = urllib.parse.unquote_plus(key)
        if sep and value and SENSITIVE_KEY.search(name):
            chunk = f"{key}={mask(name, urllib.parse.unquote_plus(value))}"
        chunks.append(chunk)
    return urllib.parse.urlunsplit(parts._replace(query="&".join(chunks)))


def find_literal_secrets(spec):
    """Paths in headers/query/body whose name looks sensitive but whose value is a fixed string."""
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    if SENSITIVE_KEY.search(key) and value.strip() and "{{" not in value:
                        found.append(f"{where}.{key}")
                else:
                    walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{where}[{index}]")

    for section in ("headers", "query", "body"):
        walk(spec.get(section), section)
    return found


# ---------------------------------------------------------------- substitution

def substitute(node, variables, missing):
    if isinstance(node, str):
        def repl(match):
            name = match.group(1)
            if name == "$guid":
                return str(uuid.uuid4())
            if name == "$now":
                return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if name in variables:
                return str(variables[name])
            if match.group(2) is not None:  # {{name|default}}
                return match.group(2).strip()
            missing.add(name)
            return match.group(0)
        return VAR_PATTERN.sub(repl, node)
    if isinstance(node, dict):
        return {k: substitute(v, variables, missing) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute(item, variables, missing) for item in node]
    return node


def extract(node, path):
    """Mini-JSONPath: '$.a.b[0].c' or 'a.b[0].c'."""
    path = path.lstrip("$").lstrip(".")
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            node = node[int(part[1:-1])]
        else:
            node = node[part]
    return node


def is_unset_optional(value, variables):
    """A query value that is only `{{name}}`, with no value and no default: an optional parameter."""
    if not isinstance(value, str):
        return False
    match = VAR_PATTERN.fullmatch(value.strip())
    return bool(match) and match.group(1) not in variables and match.group(2) is None \
        and not match.group(1).startswith("$")


# ------------------------------------------------------------------------- http

def url_host(url):
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_local(url, hosts=DEFAULT_LOCAL_HOSTS):
    return url_host(url) in {h.lower() for h in hosts}


def assert_local(url, allow_remote, hosts=DEFAULT_LOCAL_HOSTS):
    host = url_host(url)
    if not host:
        raise ToolError(f"Invalid URL (no host): {redact_url(url)}")
    if not is_local(url, hosts) and not allow_remote:
        raise ToolError(
            f"Host '{host}' is not local. This runner only talks to local hosts by default; "
            "pass --allow-remote ONLY if the user explicitly authorized that environment.")


def resolve_auth(name, config):
    """(name, entry) for the requested auth; entry is None for `none`."""
    auth = config.get("auth") or {}
    name = name or config.get("defaultAuth") or "none"
    if name == "none" and "none" not in auth:
        return name, None
    if name not in auth:
        known = ", ".join(sorted(set(auth) | {"none"}))
        raise ToolError(f"Unknown auth '{name}' (defined in config.json: {known}).")
    return name, auth[name]


def build_request(spec, env, config, overrides):
    if not spec.get("path"):
        raise ToolError("The request has no 'path'.")
    query = spec.get("query")
    if query is not None and not isinstance(query, dict):
        raise ToolError("'query' must be an object of name/value pairs.")

    variables = {**env.get("vars", {}), **overrides}
    missing = set()
    if query:
        spec = {**spec, "query": {k: v for k, v in query.items() if not is_unset_optional(v, variables)}}
    spec = substitute(spec, variables, missing)
    if missing:
        hint = " (or `seed`)" if seed_command(config) else ""
        raise ToolError(
            "Variables without a value: " + ", ".join(sorted(missing))
            + ". Set them with `env set name=value`, `--var name=value`, or `capture` from an earlier request" + hint + ".")

    url = effective_base_url(env, config) + "/" + str(spec["path"]).lstrip("/")
    params = {k: v for k, v in (spec.get("query") or {}).items() if v is not None}
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    headers = dict(spec.get("headers") or {})
    auth_name, entry = resolve_auth(spec.get("auth"), config)
    if entry is not None:
        if not isinstance(entry, dict) or not entry.get("var") or not entry.get("header"):
            raise ToolError(f"auth '{auth_name}' in config.json needs \"var\" and \"header\" (and optionally \"format\").")
        secret = variables.get(entry["var"])
        if not secret:
            hint = " or run `seed`" if seed_command(config) else ""
            raise ToolError(
                f"No value for '{entry['var']}' (needed by auth '{auth_name}'). "
                f"Set it with `env set {entry['var']}=...`{hint}, or use --auth none.")
        headers[entry["header"]] = entry.get("format", "{value}").replace("{value}", str(secret))

    body = spec.get("body")
    data = None
    if body is not None:
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = json.dumps(body).encode("utf-8")
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = "application/json"
    headers = {str(k): str(v) for k, v in headers.items()}
    return str(spec.get("method", "GET")).upper(), url, headers, data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects: a 3xx to another host would slip past the local-only guardrail."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_url(request, timeout, local):
    handlers = [_NoRedirect()]
    if local:
        handlers.append(urllib.request.ProxyHandler({}))  # never route localhost through a proxy
    return urllib.request.build_opener(*handlers).open(request, timeout=timeout)


def send_http(method, url, headers, data, timeout, local):
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    shown = redact_url(url)
    started = time.monotonic()
    try:
        with open_url(request, timeout, local) as response:
            status, raw, response_headers = response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        status, raw, response_headers = error.code, error.read(), error.headers
    except (socket.timeout, TimeoutError):
        raise ToolError(f"Request timed out after {timeout:g} s ({method} {shown}). Use --timeout to wait longer.")
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise ToolError(f"Request timed out after {timeout:g} s ({method} {shown}). Use --timeout to wait longer.")
        raise ToolError(f"Could not connect to {shown} ({error.reason}). Is the host up? Try `host status`.")
    except (OSError, http.client.HTTPException) as error:
        raise ToolError(f"Request failed ({method} {shown}): {error}")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return status, raw, response_headers, elapsed_ms


def render_and_record(project, name, method, url, status, raw, response_headers, elapsed_ms, full):
    content_type = response_headers.get("Content-Type", "")
    text = raw.decode("utf-8", errors="replace")
    parsed = None
    if "json" in content_type or text.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None

    shown = json.dumps(parsed, indent=2, ensure_ascii=False) if parsed is not None else text
    total = len(shown)
    if not full and total > BODY_LIMIT:
        shown = shown[:BODY_LIMIT] + f"\n… (truncated, {total} chars — use --full)"

    shown_url = redact_url(url)
    summary = f"→ {status}  ({elapsed_ms} ms)  {content_type or 'no content-type'}"
    retry_after = response_headers.get("Retry-After")
    if retry_after:
        summary += f"  Retry-After={retry_after}"
    location = response_headers.get("Location")
    if location and 300 <= status < 400:
        summary += f"  Location={redact_url(location)} (not followed)"
    print(f"{method} {shown_url}")
    print(summary)
    print(shown if shown else "(empty body)")

    project.last_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.\-]+", "_", name)
    record = {
        "at": datetime.now(timezone.utc).isoformat(), "method": method, "url": shown_url,
        "status": status, "elapsedMs": elapsed_ms,
        "body": redact(parsed) if parsed is not None else text[:20000],
    }
    (project.last_dir / f"{safe_name}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    entry = {k: record[k] for k in ("at", "method", "url", "status", "elapsedMs")}
    entry["name"] = name
    with (project.last_dir / "history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return parsed


def apply_capture(project, config, spec, parsed, status, env):
    captures = spec.get("capture") or {}
    if not captures:
        return
    if not (200 <= status < 300) or parsed is None:
        print(f"(capture skipped: response {status} without a JSON success body)")
        return
    extra = auth_var_names(config)
    variables = env.setdefault("vars", {})
    for var, path in captures.items():
        try:
            variables[var] = extract(parsed, path)
            print(f"captured: {var} = {mask(var, str(variables[var]), extra)}")
        except (KeyError, IndexError, TypeError):
            print(f"capture failed: '{path}' does not exist in the response")
    save_env(project, env)


# ---------------------------------------------------------------------- commands

def resolve_request_file(project, name):
    candidate = Path(name)
    if candidate.suffix != ".json":
        candidate = project.requests_dir / f"{name}.json"
    elif not candidate.is_absolute():
        in_requests = project.requests_dir / name
        candidate = in_requests if in_requests.exists() else project.root / name
    if not candidate.exists():
        raise ToolError(f"Request '{name}' not found. See `list`.")
    return candidate


def normalize_save_name(name):
    cleaned = name.strip().replace("\\", "/")
    if cleaned.endswith(".json"):
        cleaned = cleaned[:-5]
    if not cleaned or cleaned.startswith("/") or ".." in PurePosixPath(cleaned).parts or re.match(r"^[A-Za-z]:", cleaned):
        raise ToolError(f"Invalid --save name '{name}': use a relative name such as 'group/request'.")
    return cleaned


def parse_kv(pairs, sep="="):
    result = {}
    for pair in pairs or []:
        if sep not in pair:
            raise ToolError(f"Expected name{sep}value, got: {pair}")
        key, value = pair.split(sep, 1)
        result[key.strip()] = value.strip()
    return result


def execute(project, config, name, spec, env, overrides, args):
    if args.timeout <= 0:
        raise ToolError("--timeout must be greater than 0.")
    method, url, headers, data = build_request(spec, env, config, overrides)
    hosts = local_hosts(config)
    assert_local(url, args.allow_remote, hosts)
    status, raw, response_headers, elapsed_ms = send_http(method, url, headers, data, args.timeout, is_local(url, hosts))
    parsed = render_and_record(project, name, method, url, status, raw, response_headers, elapsed_ms, args.full)
    apply_capture(project, config, spec, parsed, status, env)


def cmd_run(args, project):
    config = load_config(project)
    path = resolve_request_file(project, args.name)
    spec = read_json(path, f"request '{args.name}'")
    if not isinstance(spec, dict):
        raise ToolError(f"Request '{args.name}' must be a JSON object.")
    execute(project, config, path.stem, spec, load_env(project), parse_kv(args.var), args)


def cmd_send(args, project):
    config = load_config(project)
    body = args.body
    if body and body.startswith("@"):
        try:
            body = Path(body[1:]).read_text(encoding="utf-8-sig")
        except OSError as error:
            raise ToolError(f"Cannot read the --body file: {error}")
    try:
        body = json.loads(body) if body else None
    except ValueError as error:
        raise ToolError(f"--body is not valid JSON: {error}")
    save_name = normalize_save_name(args.save) if args.save else None
    spec = {
        "method": args.method.upper(), "path": args.path, "auth": args.auth,
        "query": parse_kv(args.query) or None, "headers": parse_kv(args.header, ":") or None,
        "body": body, "capture": parse_kv(args.capture) or None,
    }
    spec = {k: v for k, v in spec.items() if v is not None}
    execute(project, config, save_name or "adhoc", spec, load_env(project), parse_kv(args.var), args)
    if save_name:
        target = project.requests_dir / f"{save_name}.json"
        write_text(target, dump_json({"name": save_name, **spec}))
        print(f"saved to {project.rel(target)}  (warning: review it — any fixed value that should be a "
              "{{variable}} was saved exactly as typed)")
        for where in find_literal_secrets(spec):
            print(f"WARNING: {where} looks like a secret with a fixed value — replace it with a {{{{variable}}}} before committing.")


def cmd_list(_args, project):
    config = load_config(project)
    default_auth = config.get("defaultAuth") or "none"
    files = sorted(project.requests_dir.rglob("*.json")) if project.requests_dir.exists() else []
    if not files:
        print("(no saved requests yet)")
    for file in files:
        rel = file.relative_to(project.requests_dir).with_suffix("").as_posix()
        try:
            spec = json.loads(file.read_text(encoding="utf-8-sig"))
            print(f"{rel:40} {spec.get('method', 'GET'):6} {spec['path']}  [{spec.get('auth') or default_auth}]  {spec.get('name', '')}")
        except (ValueError, KeyError, TypeError, AttributeError):
            print(f"{rel:40} (invalid request file)")


def cmd_show(args, project):
    print(resolve_request_file(project, args.name).read_text(encoding="utf-8-sig"))


def print_env(env, config):
    extra = auth_var_names(config)
    if env.get("baseUrl"):
        print(f"baseUrl: {redact_url(env['baseUrl'])}  [env.local.json]")
    elif config.get("baseUrl"):
        print(f"baseUrl: {redact_url(config['baseUrl'])}  [config.json]")
    else:
        print("baseUrl: (not set)")
    for key, value in sorted(env.get("vars", {}).items()):
        print(f"  {key} = {mask(key, value, extra)}")
    if not env.get("vars"):
        print("  (no variables — set them with `env set name=value`)")


def cmd_env(args, project):
    config = load_config(project)
    env = load_env(project)
    if args.action == "set":
        if not args.pairs:
            raise ToolError("`env set` needs at least one name=value pair.")
        for key, value in parse_kv(args.pairs).items():
            if key == "baseUrl":
                env["baseUrl"] = value
            else:
                env["vars"][key] = value
        save_env(project, env)
    print_env(env, config)


def cmd_history(args, project):
    history = project.last_dir / "history.jsonl"
    if not history.exists():
        print("(no history)")
        return
    for line in history.read_text(encoding="utf-8").splitlines()[-args.n:]:
        try:
            item = json.loads(line)
            print(f"{item['at'][11:19]}  {item['status']}  {item['method']:6} {item['url']}  ({item['elapsedMs']} ms)  [{item['name']}]")
        except (ValueError, KeyError, TypeError):
            continue


# -------------------------------------------------------------------------- host

def host_config(config):
    host = config.get("host")
    if not isinstance(host, dict) or not host:
        raise ToolError("`host` is not configured in this project — see `init` (it proposes a host block from the detected stack).")
    return host


def probe(url, local):
    """True when anything answers HTTP at `url` (an error status still means the host is up)."""
    try:
        open_url(urllib.request.Request(url, method="GET"), 3, local).close()
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
        return False


def newest_source(root, globs, ignore):
    """(mtime, path) of the newest file matching `globs` (relative to root) and not `ignore`."""
    newest, newest_path = 0.0, None
    for pattern in globs:
        try:
            matches = list(root.glob(pattern))
        except (NotImplementedError, ValueError) as error:
            raise ToolError(f"Invalid host.sourceGlobs pattern '{pattern}': {error}")
        for file in matches:
            rel = file.relative_to(root).as_posix()
            if any(fnmatch.fnmatchcase(rel, p) or fnmatch.fnmatchcase("/" + rel, p) for p in ignore):
                continue
            try:
                if file.is_file() and file.stat().st_mtime > newest:
                    newest, newest_path = file.stat().st_mtime, rel
            except OSError:
                continue
    return newest, newest_path


def read_host_state(project):
    path = project.last_dir / "host.json"
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError:
        return None
    return state if isinstance(state, dict) else None


def tail(path, lines):
    if not path.exists():
        return "(no log)"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def resolve_executable(command, base):
    if os.sep in command or "/" in command:
        candidate = Path(command)
        if not candidate.is_absolute():
            candidate = base / candidate
        if candidate.exists():
            return str(candidate)
        raise ToolError(f"Command not found: {command} (relative to {base})")
    found = shutil.which(command)
    if not found:
        raise ToolError(f"Command '{command}' not found in PATH.")
    return found


def process_alive(pid):
    if IS_WINDOWS:
        # os.kill(pid, 0) would TERMINATE the process on Windows — never probe with it.
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a zombie is dead for our purposes
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        if state == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def process_command(pid):
    """Command line of `pid`, or None when it cannot be determined."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        if raw:
            return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        pass
    if IS_WINDOWS:
        return None
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True).stdout.strip()
        return out or None
    except OSError:
        return None


def terminate(pid, force=False):
    if IS_WINDOWS:  # best effort: no process groups, no SIGTERM
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        pgid = os.getpgid(pid)
        if pgid == pid and pgid != os.getpgrp():
            os.killpg(pgid, sig)  # the host was started in its own session: take its children too
        else:
            os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def pids_matching(patterns):
    pids = set()
    if IS_WINDOWS or not patterns or not shutil.which("pgrep"):
        return pids
    for pattern in patterns:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
        pids.update(int(p) for p in out if p.isdigit())
    pids.discard(os.getpid())
    pids.discard(os.getppid())
    return pids


def wait_gone(pids, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline and any(process_alive(p) for p in pids):
        time.sleep(0.2)
    return [p for p in pids if process_alive(p)]


def stop_previous(project, host, start):
    """Stop the host started by a previous `host restart`: saved PID first, processPatterns as backup."""
    patterns = [p for p in (host.get("processPatterns") or []) if isinstance(p, str) and p]
    victims = set()
    state = read_host_state(project)
    pid = state.get("pid") if state else None
    if isinstance(pid, int) and process_alive(pid):
        command = process_command(pid)
        # PIDs get reused: only trust the saved one if it still looks like the host we started.
        if command is None or any(needle in command for needle in [" ".join(start), *patterns]):
            victims.add(pid)
    victims |= pids_matching(patterns)
    if not victims:
        return
    for victim in victims:
        terminate(victim)
    survivors = wait_gone(victims, 10)
    for victim in survivors:
        terminate(victim, force=True)
    survivors = wait_gone(survivors, 3)
    print(f"stopped previous host process(es): {sorted(victims)}")
    if survivors:
        print(f"WARNING: could not stop PID(s) {sorted(survivors)}; the new host may fail to bind its port.")
    if IS_WINDOWS and patterns:
        print("(note: processPatterns are not applied on Windows; only the saved PID was targeted)")


def host_restart(project, host, url, local):
    start = host.get("start")
    if not isinstance(start, list) or not start or not all(isinstance(part, str) for part in start):
        raise ToolError('host.start must be a non-empty argv list in config.json, e.g. ["npm", "run", "dev"].')
    cwd = project.root / host["cwd"] if host.get("cwd") else project.root
    if not cwd.is_dir():
        raise ToolError(f"host.cwd does not exist: {cwd}")
    try:
        timeout = float(host.get("startTimeoutSec", DEFAULT_START_TIMEOUT))
    except (TypeError, ValueError):
        raise ToolError("host.startTimeoutSec must be a number of seconds.")
    executable = resolve_executable(start[0], cwd)

    stop_previous(project, host, start)

    project.last_dir.mkdir(parents=True, exist_ok=True)
    log_path = project.last_dir / "host.log"
    options = {"cwd": str(cwd), "stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
    if IS_WINDOWS:
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        options["start_new_session"] = True
    with log_path.open("wb") as log:
        process = subprocess.Popen([executable, *start[1:]], stdout=log, **options)
    write_text(project.last_dir / "host.json", json.dumps({"pid": process.pid, "startedAt": time.time(), "start": start}))
    print(f"starting host (pid {process.pid}), log at {project.rel(log_path)} …")

    deadline = time.time() + timeout
    while time.time() < deadline:
        code = process.poll()
        if code is not None:
            print(f"host exited during startup (exit code {code}). Last log lines:")
            print(tail(log_path, 25))
            raise ToolError("host did not start")
        if probe(url, local):
            print("host responding.")
            return
        time.sleep(0.5)
    raise ToolError(f"host did not respond within {timeout:g} s — see `host logs`")


def cmd_host(args, project):
    config = load_config(project)
    host = host_config(config)
    if args.action == "logs":
        print(tail(project.last_dir / "host.log", args.n))
        return

    env = load_env(project)
    url = host.get("healthUrl") or effective_base_url(env, config)
    local = is_local(url, local_hosts(config))
    if args.action == "restart":
        host_restart(project, host, url, local)
        return

    up = probe(url, local)
    print("host: " + ("responding" if up else "DOWN") + f"  ({redact_url(url)})")
    state = read_host_state(project)
    if up and state is not None:
        globs = host.get("sourceGlobs") or []
        if globs:
            newest, path = newest_source(project.root, globs, host.get("sourceIgnore") or [])
            if newest > state.get("startedAt", 0):
                print(f"⚠ source files are newer than the host start ({path}) — the process may be OUTDATED. Run `host restart`.")
    elif up:
        print("(host was started outside this runner — cannot tell whether it is outdated)")


# -------------------------------------------------------------------------- seed

def cmd_seed(args, project):
    config = load_config(project)
    command = seed_command(config)
    if command is None:
        raise ToolError(
            'seed is not configured in this project — add {"seed": {"command": ["python3", ".claude/api/seed.py"]}} '
            "to .claude/api/config.json (run `init` first if the file does not exist). The command runs from the "
            "project root, must refuse non-local targets on its own, and prints "
            '{"baseUrl"?: "...", "vars": {...}} as JSON on stdout.')
    env = load_env(project)
    hosts = local_hosts(config)
    base = effective_base_url(env, config)
    if not is_local(base, hosts):
        raise ToolError(f"seed refused: baseUrl '{redact_url(base)}' is not a local host. seed never runs against a remote target.")

    argv = list(command) + (["--rotate"] if args.rotate else [])
    executable = resolve_executable(argv[0], project.root)
    try:
        result = subprocess.run([executable, *argv[1:]], cwd=str(project.root), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=SEED_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ToolError(f"seed command did not finish within {SEED_TIMEOUT} s.")
    except OSError as error:
        raise ToolError(f"Could not run the seed command: {error}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ToolError(f"seed command failed (exit {result.returncode}): {detail}")

    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise ToolError(
            "seed command must print a JSON object {\"baseUrl\"?: \"...\", \"vars\": {...}} on stdout "
            f"(got {len(result.stdout)} chars that are not JSON; send progress messages to stderr).")
    variables = payload.get("vars", {}) if isinstance(payload, dict) else None
    new_base = payload.get("baseUrl") if isinstance(payload, dict) else None
    if not isinstance(variables, dict) or (new_base is not None and (not isinstance(new_base, str) or not new_base)):
        raise ToolError('seed output must be {"baseUrl"?: "<url>", "vars": {"name": "value"}}.')
    if new_base is not None:
        if not is_local(new_base, hosts):
            raise ToolError(f"seed refused: the command returned a non-local baseUrl '{redact_url(new_base)}'.")
        env["baseUrl"] = new_base
    env["vars"].update(variables)
    save_env(project, env)
    print(f"seed ok — merged {len(variables)} variable(s) into env.local.json: {', '.join(sorted(variables)) or '(none)'}")
    print_env(env, config)


# -------------------------------------------------------------------------- init

SKIP_DIRS = {"node_modules", "bin", "obj", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".claude"}


def find_files(root, matches, max_depth=2):
    """Files whose name satisfies `matches`, at the root or up to `max_depth` levels below, shallowest first."""
    found = []
    level = [Path(root)]
    for _ in range(max_depth + 1):
        next_level = []
        for directory in level:
            try:
                entries = sorted(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_file() and matches(entry.name):
                    found.append(entry)
                elif entry.is_dir() and entry.name not in SKIP_DIRS:
                    next_level.append(entry)
        level = next_level
    return found


def read_launch_url(folder):
    """First http:// applicationUrl in Properties/launchSettings.json, if any."""
    try:
        data = json.loads((folder / "Properties" / "launchSettings.json").read_text(encoding="utf-8-sig"))
        for profile in data.get("profiles", {}).values():
            for url in str(profile.get("applicationUrl", "")).split(";"):
                if url.strip().startswith("http://"):
                    return url.strip()
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return None


def compiled_source_globs(root):
    return ["src/**/*.cs"] if (root / "src").is_dir() else ["**/*.cs"]


def detect_stack(root):
    """Best-effort guess of how to run the project's local HTTP server; None when nothing matches."""
    root = Path(root)

    def relative(folder):
        rel = folder.relative_to(root).as_posix()
        return {} if rel == "." else {"cwd": rel}

    functions = find_files(root, lambda name: name == "host.json")
    if functions:
        folder = functions[0].parent
        host = {**relative(folder), "start": ["func", "host", "start", "--port", "7071"],
                "healthUrl": "http://localhost:7071/", "processPatterns": ["func host start"]}
        if any(folder.glob("*.csproj")):
            host["processPatterns"].append(f"{folder.name}.dll")
            host["sourceGlobs"] = compiled_source_globs(root)
            host["sourceIgnore"] = ["**/obj/**", "**/bin/**"]
        host["startTimeoutSec"] = 180
        return {"stack": "Azure Functions", "baseUrl": "http://localhost:7071/api", "host": host}

    for project_file in find_files(root, lambda name: name.endswith(".csproj")):
        try:
            text = project_file.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if "Microsoft.NET.Sdk.Web" not in text:
            continue
        folder = project_file.parent
        url = read_launch_url(folder) or "http://localhost:5000"
        host = {**relative(folder), "start": ["dotnet", "run"], "healthUrl": url + "/",
                "processPatterns": ["dotnet run", f"{project_file.stem}.dll"],
                "sourceGlobs": compiled_source_globs(root), "sourceIgnore": ["**/obj/**", "**/bin/**"],
                "startTimeoutSec": 180}
        return {"stack": "ASP.NET Core (dotnet run)", "baseUrl": url, "host": host}

    for package_file in find_files(root, lambda name: name == "package.json"):
        try:
            data = json.loads(package_file.read_text(encoding="utf-8-sig"))
            scripts = data.get("scripts") or {}
            dependencies = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        except (OSError, ValueError, AttributeError, TypeError):
            continue
        if "dev" not in scripts:
            continue
        url = "http://localhost:5173" if "vite" in dependencies else "http://localhost:3000"
        # No sourceGlobs: `npm run dev` servers reload on change, so staleness is not a concern.
        host = {**relative(package_file.parent), "start": ["npm", "run", "dev"], "healthUrl": url + "/",
                "processPatterns": ["npm run dev"], "startTimeoutSec": 60}
        return {"stack": "Node (npm run dev)", "baseUrl": url, "host": host}
    return None


def build_config(base_url, default_auth, host):
    config = {
        "baseUrl": base_url,
        "localHosts": list(DEFAULT_LOCAL_HOSTS),
        "defaultAuth": default_auth,
        "auth": {
            "apikey": {"var": "apiKey", "header": "X-API-Key", "format": "{value}"},
            "bearer": {"var": "bearerToken", "header": "Authorization", "format": "Bearer {value}"},
            "none": None,
        },
    }
    if host:
        config["host"] = host
    return config


def ensure_gitignore(root):
    """Append the entries that are not yet ignored; returns the ones it added."""
    path = Path(root) / ".gitignore"
    text = path.read_bytes().decode("utf-8", errors="replace") if path.exists() else ""
    present = {line.strip().lstrip("/").rstrip("/") for line in text.splitlines()}
    missing = [entry for entry in GITIGNORE_ENTRIES if entry.rstrip("/") not in present]
    if missing:
        prefix = "" if not text or text.endswith("\n") else "\n"
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(prefix + "\n".join(missing) + "\n")
    return missing


def cmd_init(args, project):
    project.api_dir.mkdir(parents=True, exist_ok=True)
    had_env = project.env_file.exists()
    legacy_env = load_env(project) if had_env else None
    lines = [f"init: {project.root}"]
    proposal = None
    wrote_config = False

    if project.config_file.exists() and not args.force:
        lines.append("  config.json      kept — already exists (use --force to overwrite)")
    else:
        wrote_config = True
        proposal = detect_stack(project.root)
        base_url = (legacy_env or {}).get("baseUrl") or (proposal["baseUrl"] if proposal else "http://localhost:8080")
        known = (legacy_env or {}).get("vars", {})
        default_auth = "apikey" if "apiKey" in known else "bearer" if "bearerToken" in known else "none"
        config = build_config(base_url, default_auth, proposal["host"] if proposal else None)
        write_text(project.config_file, dump_json(config))
        lines.append("  config.json      created")

    if had_env:
        try:
            os.chmod(project.env_file, 0o600)
        except OSError:
            pass
        lines.append("  env.local.json   kept — existing file preserved (mode 600)")
    else:
        save_env(project, {"vars": {}})
        lines.append("  env.local.json   created (mode 600)")

    if project.requests_dir.exists():
        count = len(list(project.requests_dir.rglob("*.json")))
        lines.append(f"  requests/        preserved ({count} saved request(s))")

    added = ensure_gitignore(project.root)
    lines.append("  .gitignore       added: " + ", ".join(added) if added else "  .gitignore       already up to date")
    print("\n".join(lines))

    if proposal:
        print(f"\nDetected stack: {proposal['stack']}. Proposed baseUrl and host (REVIEW before relying on them):")
        print(json.dumps({"baseUrl": proposal["baseUrl"], "host": proposal["host"]}, indent=2, ensure_ascii=False))
    elif wrote_config:
        print("\nNo stack detected — no `host` block was written (`host` commands stay unavailable until you add one).")
    print("\nNext: review .claude/api/config.json (baseUrl, auth entries), then set secrets with "
          "`env set <var>=<value>`. Add a `seed` block if the project has a way to prepare local dev data.")


# -------------------------------------------------------------------------- main

def build_parser():
    parser = argparse.ArgumentParser(description="Runner of the `api` skill: exploratory HTTP client.")
    parser.add_argument("--root", default=None, help="project root (default: $CLAUDE_PROJECT_DIR, then the nearest dir with .claude/ or .git)")
    sub = parser.add_subparsers(dest="command", required=True)

    root_option = argparse.ArgumentParser(add_help=False)
    root_option.add_argument("--root", default=argparse.SUPPRESS, help="project root (same as before the command)")

    def add(name, help_text):
        return sub.add_parser(name, help=help_text, parents=[root_option])

    def common(p):
        p.add_argument("--var", action="append", help="override a variable: name=value")
        p.add_argument("--full", action="store_true", help="do not truncate the response body")
        p.add_argument("--allow-remote", action="store_true", help="allow a non-local host (only with the user's explicit authorization)")
        p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"seconds to wait for the response (default {DEFAULT_TIMEOUT:g})")

    init = add("init", "create .claude/api/ (config.json, env.local.json) and update .gitignore")
    init.add_argument("--force", action="store_true", help="overwrite an existing config.json")
    init.set_defaults(func=cmd_init)

    run = add("run", "run a saved request")
    run.add_argument("name", help="name under requests/ (without .json) or a path to a .json file")
    common(run)
    run.set_defaults(func=cmd_run)

    snd = add("send", "ad-hoc request (optionally saved)")
    snd.add_argument("method")
    snd.add_argument("path", help="relative to baseUrl, e.g. /v1/items")
    snd.add_argument("--body", help="inline JSON or @file")
    snd.add_argument("--query", action="append", help="k=v")
    snd.add_argument("--header", action="append", help="Name:value")
    snd.add_argument("--auth", default=None, help="auth name from config.json, or none (default: config defaultAuth)")
    snd.add_argument("--capture", action="append", help="var=$.path.in.response")
    snd.add_argument("--save", help="save as requests/<name>.json")
    common(snd)
    snd.set_defaults(func=cmd_send)

    add("list", "list saved requests").set_defaults(func=cmd_list)
    show = add("show", "print the JSON of a saved request")
    show.add_argument("name")
    show.set_defaults(func=cmd_show)

    env = add("env", "show or change variables (baseUrl is special)")
    env.add_argument("action", choices=["show", "set"])
    env.add_argument("pairs", nargs="*", help="name=value ...")
    env.set_defaults(func=cmd_env)

    hist = add("history", "latest calls")
    hist.add_argument("-n", type=int, default=15)
    hist.set_defaults(func=cmd_history)

    host = add("host", "status / restart / logs of the local dev host (config.json `host`)")
    host.add_argument("action", choices=["status", "restart", "logs"])
    host.add_argument("-n", type=int, default=40, help="log lines to show")
    host.set_defaults(func=cmd_host)

    seed = add("seed", "run the project's seed hook (config.json `seed.command`) and merge its output into env.local.json")
    seed.add_argument("--rotate", action="store_true", help="forwarded to the seed command (e.g. issue a new credential)")
    seed.set_defaults(func=cmd_seed)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    args = build_parser().parse_args(argv)
    try:
        args.func(args, Project(resolve_root(args.root)))
    except ToolError as error:
        print(f"ERRO: {error}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
