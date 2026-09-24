"""Tests for scripts/api.py — standard library only (unittest).

Run from the repository root:

    python3 -m unittest discover -s plugins/workflow/skills/api/tests -v

The end-to-end tests start a throw-away http.server on 127.0.0.1 and drive the runner as a
subprocess, exactly as Claude does. Nothing here touches the network or a real project.
"""
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "api.py"
sys.path.insert(0, str(SCRIPT.parent))
import api  # noqa: E402

API_KEY = "ABCD1234EFGH5678IJKL"  # 20 chars
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
NOW_RE = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
POSIX = os.name == "posix"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_cli(root, *args, root_flag=True, cwd=None, env=None):
    """Run the runner as a subprocess, like Claude does."""
    full_env = {k: v for k, v in os.environ.items()
                if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy", "claude_project_dir")}
    full_env["PYTHONIOENCODING"] = "utf-8"
    full_env.update(env or {})
    command = [sys.executable, str(SCRIPT)]
    if root_flag:
        command += ["--root", str(root)]
    command += [str(arg) for arg in args]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                          env=full_env, cwd=str(cwd or root), timeout=120)


# ---------------------------------------------------------------------- unit tests

class SubstituteTests(unittest.TestCase):
    def sub(self, text, variables=None):
        missing = set()
        return api.substitute(text, variables or {}, missing), missing

    def test_variable(self):
        self.assertEqual(self.sub("id={{id}}", {"id": 5}), ("id=5", set()))

    def test_variable_with_spaces(self):
        self.assertEqual(self.sub("{{ id }}", {"id": "x"}), ("x", set()))

    def test_default_used_when_missing(self):
        self.assertEqual(self.sub("{{count|20}}"), ("20", set()))

    def test_variable_wins_over_default(self):
        self.assertEqual(self.sub("{{count|20}}", {"count": "5"}), ("5", set()))

    def test_empty_default(self):
        self.assertEqual(self.sub("x{{y|}}z"), ("xz", set()))

    def test_guid_is_new_every_time(self):
        first, _ = self.sub("{{$guid}}")
        second, _ = self.sub("{{$guid}}")
        self.assertRegex(first, "^" + UUID_RE + "$")
        self.assertNotEqual(first, second)

    def test_now_is_utc_iso8601(self):
        value, _ = self.sub("{{$now}}")
        self.assertRegex(value, "^" + NOW_RE + "$")

    def test_missing_is_reported_and_placeholder_kept(self):
        text, missing = self.sub("{{a}}/{{b}}", {"a": "1"})
        self.assertEqual(missing, {"b"})
        self.assertEqual(text, "1/{{b}}")

    def test_nested_structures(self):
        node = {"a": ["{{x}}", {"b": "{{y|d}}"}], "n": 3}
        self.assertEqual(self.sub(node, {"x": "1"})[0], {"a": ["1", {"b": "d"}], "n": 3})


class BuildRequestTests(unittest.TestCase):
    CONFIG = {
        "baseUrl": "http://localhost:1234/api",
        "defaultAuth": "none",
        "auth": {
            "apikey": {"var": "apiKey", "header": "Authorization", "format": "ApiKey {value}"},
            "bearer": {"var": "bearerToken", "header": "Authorization", "format": "Bearer {value}"},
            "none": None,
        },
    }

    def build(self, spec, variables=None, overrides=None, config=None, env_extra=None):
        env = {"vars": variables or {}, **(env_extra or {})}
        return api.build_request(spec, env, config or self.CONFIG, overrides or {})

    def test_optional_query_param_is_omitted(self):
        _, url, _, _ = self.build({"path": "/s", "query": {"upc": "{{upc}}", "page": "1"}})
        self.assertEqual(url, "http://localhost:1234/api/s?page=1")

    def test_optional_query_param_kept_when_set(self):
        _, url, _, _ = self.build({"path": "/s", "query": {"upc": "{{upc}}"}}, overrides={"upc": "9"})
        self.assertEqual(url, "http://localhost:1234/api/s?upc=9")

    def test_query_default_is_applied_not_omitted(self):
        _, url, _, _ = self.build({"path": "/s", "query": {"count": "{{count|20}}"}})
        self.assertTrue(url.endswith("?count=20"))

    def test_guid_alone_in_query_is_generated_not_omitted(self):
        _, url, _, _ = self.build({"path": "/s", "query": {"id": "{{$guid}}"}})
        self.assertRegex(url, r"\?id=" + UUID_RE + "$")

    def test_query_with_extra_text_and_missing_var_is_an_error(self):
        with self.assertRaises(api.ToolError) as caught:
            self.build({"path": "/s", "query": {"q": "x{{y}}"}})
        self.assertIn("y", str(caught.exception))

    def test_missing_variable_in_path_names_the_variable(self):
        with self.assertRaises(api.ToolError) as caught:
            self.build({"path": "/items/{{itemId}}/parts/{{partId}}"})
        self.assertIn("itemId, partId", str(caught.exception))

    def test_missing_variable_in_body_is_an_error(self):
        with self.assertRaises(api.ToolError) as caught:
            self.build({"method": "POST", "path": "/i", "body": {"a": ["{{nope}}"]}})
        self.assertIn("nope", str(caught.exception))

    def test_path_that_already_has_a_query_string(self):
        _, url, _, _ = self.build({"path": "/x?a=1", "query": {"b": "2"}})
        self.assertTrue(url.endswith("/x?a=1&b=2"))

    def test_auth_format_and_header_come_from_config(self):
        _, _, headers, _ = self.build({"path": "/x", "auth": "apikey"}, variables={"apiKey": "k1"})
        self.assertEqual(headers["Authorization"], "ApiKey k1")

    def test_default_auth_applies_when_the_request_does_not_say(self):
        config = {**self.CONFIG, "defaultAuth": "bearer"}
        _, _, headers, _ = self.build({"path": "/x"}, variables={"bearerToken": "t"}, config=config)
        self.assertEqual(headers["Authorization"], "Bearer t")

    def test_auth_none_sends_no_credentials(self):
        _, _, headers, _ = self.build({"path": "/x", "auth": "none"}, variables={"apiKey": "k"})
        self.assertNotIn("Authorization", headers)

    def test_missing_auth_secret_is_an_error(self):
        with self.assertRaises(api.ToolError) as caught:
            self.build({"path": "/x", "auth": "apikey"})
        self.assertIn("apiKey", str(caught.exception))

    def test_unknown_auth_is_an_error(self):
        with self.assertRaises(api.ToolError) as caught:
            self.build({"path": "/x", "auth": "magic"})
        self.assertIn("Unknown auth 'magic'", str(caught.exception))

    def test_json_body_sets_content_type_once(self):
        _, _, headers, data = self.build({"method": "post", "path": "/x", "body": {"a": 1},
                                          "headers": {"content-type": "application/vnd.x+json"}})
        self.assertEqual(json.loads(data), {"a": 1})
        self.assertEqual([k for k in headers if k.lower() == "content-type"], ["content-type"])

    def test_method_is_upper_cased(self):
        method, _, _, _ = self.build({"method": "post", "path": "/x"})
        self.assertEqual(method, "POST")

    def test_env_base_url_overrides_config(self):
        _, url, _, _ = self.build({"path": "/x"}, env_extra={"baseUrl": "http://localhost:9/z/"})
        self.assertEqual(url, "http://localhost:9/z/x")

    def test_no_base_url_anywhere_is_an_error(self):
        with self.assertRaises(api.ToolError):
            api.build_request({"path": "/x"}, {"vars": {}}, {}, {})

    def test_request_without_path_is_an_error(self):
        with self.assertRaises(api.ToolError):
            self.build({"method": "GET"})


class ExtractTests(unittest.TestCase):
    DATA = {"a": {"b": [{"c": 1}, {"c": 2}]}, "list": [{"id": "x"}]}

    def test_dotted_path_with_index(self):
        self.assertEqual(api.extract(self.DATA, "$.a.b[0].c"), 1)
        self.assertEqual(api.extract(self.DATA, "$.a.b[1].c"), 2)

    def test_leading_dollar_is_optional(self):
        self.assertEqual(api.extract(self.DATA, "a.b[1].c"), 2)

    def test_root_array_index(self):
        self.assertEqual(api.extract([{"id": "z"}], "$[0].id"), "z")

    def test_whole_document(self):
        self.assertEqual(api.extract(self.DATA, "$"), self.DATA)

    def test_missing_key_raises(self):
        with self.assertRaises(KeyError):
            api.extract(self.DATA, "$.nope")

    def test_index_out_of_range_raises(self):
        with self.assertRaises(IndexError):
            api.extract(self.DATA, "$.a.b[5]")


class MaskTests(unittest.TestCase):
    def test_mask_format(self):
        self.assertEqual(api.mask("apiKey", "A" * 64), "AAAA…(64 chars)")

    def test_non_sensitive_key_is_untouched(self):
        self.assertEqual(api.mask("tenantId", "abc-123"), "abc-123")

    def test_empty_and_non_string_values_are_untouched(self):
        self.assertEqual(api.mask("password", ""), "")
        self.assertEqual(api.mask("token", 5), 5)

    def test_every_documented_key_is_sensitive(self):
        for key in ("mySecret", "accessToken", "Password", "apikey", "api_key", "X-Api-Key", "Authorization"):
            self.assertNotEqual(api.mask(key, "0123456789"), "0123456789", key)

    def test_extra_names_are_masked_too(self):
        self.assertEqual(api.mask("myCred", "0123456789", extra={"myCred"}), "0123…(10 chars)")

    def test_redact_walks_nested_structures(self):
        node = {"user": {"name": "ann", "password": "hunter2hunter2"}, "items": [{"token": "abcdefgh"}], "n": 1}
        self.assertEqual(api.redact(node), {
            "user": {"name": "ann", "password": "hunt…(14 chars)"},
            "items": [{"token": "abcd…(8 chars)"}], "n": 1})

    def test_redact_does_not_mutate_its_input(self):
        node = {"token": "abcdefgh"}
        api.redact(node)
        self.assertEqual(node, {"token": "abcdefgh"})

    def test_redact_url_masks_sensitive_query_values_only(self):
        self.assertEqual(api.redact_url("http://h:1/x?token=abcdefgh1234&page=2&api_key=zzzzzzzzzz"),
                         "http://h:1/x?token=abcd…(12 chars)&page=2&api_key=zzzz…(10 chars)")

    def test_redact_url_without_query_is_unchanged(self):
        self.assertEqual(api.redact_url("http://h/x"), "http://h/x")

    def test_redact_url_keeps_empty_sensitive_values(self):
        self.assertEqual(api.redact_url("http://h/x?token=&a=1"), "http://h/x?token=&a=1")

    def test_find_literal_secrets(self):
        spec = {"headers": {"Authorization": "Bearer x", "Accept": "*/*"},
                "query": {"token": "{{token}}"}, "body": {"nested": {"password": "pw"}, "ok": "fine"}}
        self.assertEqual(sorted(api.find_literal_secrets(spec)), ["body.nested.password", "headers.Authorization"])


class AssertLocalTests(unittest.TestCase):
    def test_local_hosts_pass(self):
        for url in ("http://localhost:7071/api", "http://127.0.0.1/x", "http://[::1]:8080/x", "http://LOCALHOST/x"):
            api.assert_local(url, False)

    def test_remote_host_is_refused(self):
        with self.assertRaises(api.ToolError) as caught:
            api.assert_local("http://example.invalid/api", False)
        self.assertIn("not local", str(caught.exception))

    def test_allow_remote_lets_it_through(self):
        api.assert_local("http://example.invalid/api", True)

    def test_local_hosts_come_from_config(self):
        api.assert_local("http://sqlbox/x", False, hosts=("sqlbox",))
        with self.assertRaises(api.ToolError):
            api.assert_local("http://localhost/x", False, hosts=("sqlbox",))

    def test_url_without_host_is_invalid_even_with_allow_remote(self):
        with self.assertRaises(api.ToolError) as caught:
            api.assert_local("not a url", True)
        self.assertIn("Invalid URL", str(caught.exception))


class ResolveRootTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()

    def test_explicit_root_wins_over_environment(self):
        one, two = self.tmp / "one", self.tmp / "two"
        one.mkdir()
        two.mkdir()
        self.assertEqual(api.resolve_root(str(one), environ={"CLAUDE_PROJECT_DIR": str(two)}), one)

    def test_environment_variable_wins_over_walking_up(self):
        proj, other = self.tmp / "proj", self.tmp / "other"
        (proj / ".git").mkdir(parents=True)
        other.mkdir()
        self.assertEqual(api.resolve_root(None, environ={"CLAUDE_PROJECT_DIR": str(other)}, cwd=proj), other)

    def test_walks_up_to_git(self):
        deep = self.tmp / "proj" / "a" / "b"
        deep.mkdir(parents=True)
        (self.tmp / "proj" / ".git").mkdir()
        self.assertEqual(api.resolve_root(None, environ={}, cwd=deep), self.tmp / "proj")

    def test_walks_up_to_claude_dir(self):
        deep = self.tmp / "proj" / "a"
        deep.mkdir(parents=True)
        (self.tmp / "proj" / ".claude").mkdir()
        self.assertEqual(api.resolve_root(None, environ={}, cwd=deep), self.tmp / "proj")

    def test_nearest_marker_wins(self):
        (self.tmp / "proj" / ".git").mkdir(parents=True)
        (self.tmp / "proj" / "sub" / "x").mkdir(parents=True)
        (self.tmp / "proj" / "sub" / ".claude").mkdir()
        self.assertEqual(api.resolve_root(None, environ={}, cwd=self.tmp / "proj" / "sub" / "x"), self.tmp / "proj" / "sub")

    def test_git_worktree_file_counts(self):
        (self.tmp / "wt").mkdir()
        (self.tmp / "wt" / ".git").write_text("gitdir: /elsewhere\n")
        self.assertEqual(api.resolve_root(None, environ={}, cwd=self.tmp / "wt"), self.tmp / "wt")

    def test_no_marker_found(self):
        self.assertIsNone(api.find_project_root(self.tmp, markers=("__no_such_marker__",)))

    def test_not_found_raises_with_a_hint(self):
        with mock.patch.object(api, "find_project_root", return_value=None):
            with self.assertRaises(api.ToolError) as caught:
                api.resolve_root(None, environ={}, cwd=self.tmp)
        self.assertIn("--root", str(caught.exception))

    def test_explicit_root_must_exist(self):
        with self.assertRaises(api.ToolError):
            api.resolve_root(str(self.tmp / "missing"), environ={})

    def test_user_level_claude_dir_is_not_a_project(self):
        home = self.tmp / "home"
        (home / ".claude").mkdir(parents=True)
        (home / "work").mkdir()
        with mock.patch.object(Path, "home", return_value=home):
            found = api.find_project_root(home / "work", markers=(".claude",))
        self.assertNotEqual(found, home)


# ------------------------------------------------------------------ e2e infrastructure

class Handler(BaseHTTPRequestHandler):
    hits = []

    def log_message(self, *args):
        pass

    def _send(self, status, payload, headers=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass  # client gave up (timeout test)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        Handler.hits.append((method, self.path))
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/ping":
            return self._send(200, {"ok": True})
        if path == "/api/echo":
            return self._send(200, {"method": method, "path": self.path,
                                    "authorization": self.headers.get("Authorization"), "body": body})
        if path == "/api/items" and method == "POST":
            return self._send(201, {"id": "new-1", "token": "TOKENVALUE1234567890", "received": body})
        if path == "/api/items/new-1":
            return self._send(200, {"id": "new-1"})
        if path == "/api/list":
            return self._send(200, [{"id": "abc"}, {"id": "def"}])
        if path == "/api/forbidden":
            return self._send(403, {"error": "nope"})
        if path == "/api/limited":
            return self._send(429, {"error": "slow down"}, {"Retry-After": "7"})
        if path == "/api/big":
            return self._send(200, {"data": "x" * 6000})
        if path == "/api/redirect":
            return self._send(302, None, {"Location": "http://example.invalid/elsewhere"}, raw=b"")
        if path == "/api/slow":
            time.sleep(1.5)
            return self._send(200, {"slow": True})
        return self._send(404, {"error": "not found"})


class ProjectCase(unittest.TestCase):
    """A throw-away project directory (with a .git marker) per test."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / ".git").mkdir()
        self.api_dir = self.root / ".claude" / "api"

    def write_config(self, config):
        self.api_dir.mkdir(parents=True, exist_ok=True)
        (self.api_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    def write_env(self, env):
        self.api_dir.mkdir(parents=True, exist_ok=True)
        (self.api_dir / "env.local.json").write_text(json.dumps(env, indent=2), encoding="utf-8")

    def read_env(self):
        return json.loads((self.api_dir / "env.local.json").read_text(encoding="utf-8"))

    def read_last(self, name):
        return json.loads((self.api_dir / ".last" / f"{name}.json").read_text(encoding="utf-8"))

    def history(self):
        path = self.api_dir / ".last" / "history.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def save_request(self, name, spec):
        target = self.api_dir / "requests" / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    def cli(self, *args, **kwargs):
        return run_cli(self.root, *args, **kwargs)


class ServerCase(ProjectCase):
    """ProjectCase + a local http.server, with a config that authenticates like an ApiKey API."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/api"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        super().setUp()
        Handler.hits.clear()
        self.write_config({
            "baseUrl": self.base, "defaultAuth": "apikey",
            "auth": {"apikey": {"var": "apiKey", "header": "Authorization", "format": "ApiKey {value}"},
                     "bearer": {"var": "bearerToken", "header": "Authorization", "format": "Bearer {value}"},
                     "none": None}})
        self.write_env({"vars": {"apiKey": API_KEY}})

    def ok(self, *args, **kwargs):
        result = self.cli(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result


# ------------------------------------------------------------------------ e2e: send

class SendTests(ServerCase):
    def test_get_prints_method_url_status_time_type_and_indented_body(self):
        out = self.ok("send", "GET", "/ping").stdout
        self.assertIn(f"GET {self.base}/ping", out)
        self.assertIn("→ 200", out)
        self.assertRegex(out, r"\(\d+ ms\)")
        self.assertIn("application/json", out)
        self.assertIn('"ok": true', out)

    def test_records_last_and_history(self):
        self.ok("send", "GET", "/ping")
        entry = self.history()[-1]
        self.assertEqual((entry["name"], entry["status"], entry["method"]), ("adhoc", 200, "GET"))
        self.assertEqual(self.read_last("adhoc")["status"], 200)

    def test_auth_header_is_sent_but_masked_on_disk(self):
        out = self.ok("send", "GET", "/echo").stdout
        self.assertIn("ApiKey " + API_KEY, out)  # what the server really received
        on_disk = (self.api_dir / ".last" / "adhoc.json").read_text(encoding="utf-8")
        self.assertNotIn(API_KEY, on_disk)
        self.assertIn("ApiK…(27 chars)", on_disk)

    def test_auth_none_sends_no_header(self):
        out = self.ok("send", "GET", "/echo", "--auth", "none").stdout
        self.assertIn('"authorization": null', out)

    def test_unknown_auth_name(self):
        result = self.cli("send", "GET", "/echo", "--auth", "nope")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown auth 'nope'", result.stderr)

    def test_missing_auth_secret_refuses_without_calling(self):
        self.write_env({"vars": {}})
        result = self.cli("send", "GET", "/ping")
        self.assertEqual(result.returncode, 2)
        self.assertIn("apiKey", result.stderr)
        self.assertEqual(Handler.hits, [])

    def test_post_with_inline_json_body(self):
        out = self.ok("send", "POST", "/items", "--body", '{"name":"widget"}').stdout
        self.assertIn("→ 201", out)
        self.assertIn('"name": "widget"', out)

    def test_body_from_file(self):
        (self.root / "body.json").write_text('{"fromFile": true}', encoding="utf-8")
        out = self.ok("send", "POST", "/items", "--body", "@body.json").stdout
        self.assertIn('"fromFile": true', out)

    def test_invalid_body_is_a_usage_error(self):
        result = self.cli("send", "POST", "/items", "--body", "{nope")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--body is not valid JSON", result.stderr)

    def test_query_and_header_options(self):
        out = self.ok("send", "GET", "/echo", "--query", "count=5", "--header", "X-Trace: abc").stdout
        self.assertIn("count=5", out)
        self.assertEqual(Handler.hits[-1], ("GET", "/api/echo?count=5"))

    def test_variables_default_and_override(self):
        self.ok("send", "GET", "/echo", "--query", "a={{a|dflt}}", "--query", "b={{b}}", "--var", "b=bee")
        self.assertEqual(Handler.hits[-1], ("GET", "/api/echo?a=dflt&b=bee"))

    def test_missing_path_variable_is_refused_and_named(self):
        result = self.cli("send", "GET", "/items/{{itemId}}")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("ERRO:"), result.stderr)
        self.assertIn("itemId", result.stderr)
        self.assertEqual(Handler.hits, [], "the placeholder must never be sent")

    def test_guid_and_now_are_generated_per_call(self):
        body = '{"id":"{{$guid}}","at":"{{$now}}"}'
        first = self.ok("send", "POST", "/echo", "--body", body).stdout
        second = self.ok("send", "POST", "/echo", "--body", body).stdout
        ids = [re.search(r'"id": "(' + UUID_RE + ')"', text).group(1) for text in (first, second)]
        self.assertNotEqual(*ids)
        self.assertRegex(first, r'"at": "' + NOW_RE + '"')

    def test_error_status_is_not_a_tool_error(self):
        result = self.ok("send", "GET", "/forbidden")
        self.assertIn("→ 403", result.stdout)
        self.assertIn('"error": "nope"', result.stdout)

    def test_retry_after_is_shown(self):
        out = self.ok("send", "GET", "/limited").stdout
        self.assertIn("→ 429", out)
        self.assertIn("Retry-After=7", out)

    def test_long_body_is_truncated_unless_full(self):
        short = self.ok("send", "GET", "/big").stdout
        self.assertIn("truncated", short)
        self.assertIn("--full", short)
        self.assertLess(len(short), 5000)
        full = self.ok("send", "GET", "/big", "--full").stdout
        self.assertNotIn("truncated", full)
        self.assertGreater(len(full), 6000)

    def test_redirect_is_shown_not_followed(self):
        out = self.ok("send", "GET", "/redirect").stdout
        self.assertIn("→ 302", out)
        self.assertIn("Location=http://example.invalid/elsewhere", out)
        self.assertIn("not followed", out)

    def test_timeout_option(self):
        result = self.cli("send", "GET", "/slow", "--timeout", "0.3")
        self.assertEqual(result.returncode, 2)
        self.assertIn("timed out", result.stderr)

    def test_non_positive_timeout_is_rejected(self):
        result = self.cli("send", "GET", "/ping", "--timeout", "0")
        self.assertEqual(result.returncode, 2)

    def test_connection_refused_is_a_clear_error(self):
        self.write_config({"baseUrl": f"http://127.0.0.1:{free_port()}/api", "defaultAuth": "none"})
        result = self.cli("send", "GET", "/ping")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Could not connect", result.stderr)

    def test_secret_in_query_is_sent_but_masked_everywhere_it_is_persisted_or_shown(self):
        out = self.ok("send", "GET", "/ping", "--query", "token=SECRETSECRET1234", "--query", "page=2").stdout
        self.assertEqual(Handler.hits[-1], ("GET", "/api/ping?token=SECRETSECRET1234&page=2"))
        self.assertIn("token=SECR…(16 chars)&page=2", out)
        self.assertNotIn("SECRETSECRET1234", out)
        for text in ((self.api_dir / ".last" / "adhoc.json").read_text(encoding="utf-8"),
                     (self.api_dir / ".last" / "history.jsonl").read_text(encoding="utf-8")):
            self.assertNotIn("SECRETSECRET1234", text)
            self.assertIn("token=SECR…(16 chars)", text)


# --------------------------------------------------------------------- e2e: capture

class CaptureTests(ServerCase):
    def test_capture_feeds_the_next_call(self):
        out = self.ok("send", "POST", "/items", "--body", "{}", "--capture", "itemId=$.id").stdout
        self.assertIn("captured: itemId = new-1", out)
        self.assertEqual(self.read_env()["vars"]["itemId"], "new-1")
        self.ok("send", "GET", "/items/{{itemId}}")
        self.assertEqual(Handler.hits[-1], ("GET", "/api/items/new-1"))

    def test_captured_secret_is_masked_in_the_capture_line(self):
        out = self.ok("send", "POST", "/items", "--body", "{}", "--capture", "apiToken=$.token").stdout
        line = next(l for l in out.splitlines() if l.startswith("captured:"))
        self.assertIn("TOKE…(20 chars)", line)
        self.assertEqual(self.read_env()["vars"]["apiToken"], "TOKENVALUE1234567890")

    def test_capture_from_a_root_array(self):
        self.ok("send", "GET", "/list", "--capture", "first=$[0].id")
        self.assertEqual(self.read_env()["vars"]["first"], "abc")

    def test_capture_is_skipped_on_error_and_keeps_the_old_value(self):
        self.write_env({"vars": {"apiKey": API_KEY, "itemId": "keep"}})
        out = self.ok("send", "GET", "/forbidden", "--capture", "itemId=$.error").stdout
        self.assertIn("→ 403", out)
        self.assertIn("capture skipped", out)
        self.assertEqual(self.read_env()["vars"]["itemId"], "keep")

    def test_capture_with_a_bad_path_warns_and_sets_nothing(self):
        out = self.ok("send", "GET", "/ping", "--capture", "x=$.nope").stdout
        self.assertIn("capture failed", out)
        self.assertNotIn("x", self.read_env()["vars"])

    def test_capture_declared_in_a_saved_request(self):
        self.save_request("create", {"method": "POST", "path": "/items", "body": {"a": 1},
                                     "capture": {"itemId": "$.id"}})
        self.ok("run", "create")
        self.assertEqual(self.read_env()["vars"]["itemId"], "new-1")


# -------------------------------------------------------------- e2e: saved requests

class SavedRequestTests(ServerCase):
    def test_save_writes_a_secret_free_file_and_run_replays_it(self):
        out = self.ok("send", "GET", "/ping", "--query", "page=1", "--save", "group/ping-test").stdout
        target = self.api_dir / "requests" / "group" / "ping-test.json"
        self.assertIn("saved to .claude/api/requests/group/ping-test.json", out)
        self.assertIn("review", out)
        text = target.read_text(encoding="utf-8")
        saved = json.loads(text)
        self.assertEqual((saved["name"], saved["method"], saved["path"], saved["query"]),
                         ("group/ping-test", "GET", "/ping", {"page": "1"}))
        self.assertNotIn("auth", saved)
        self.assertNotIn(API_KEY, text)
        replay = self.ok("run", "group/ping-test").stdout
        self.assertIn("→ 200", replay)
        self.assertEqual(Handler.hits[-1], ("GET", "/api/ping?page=1"))

    def test_save_keeps_placeholders_unresolved(self):
        self.write_env({"vars": {"apiKey": API_KEY, "itemId": "new-1"}})
        self.ok("send", "GET", "/items/{{itemId}}", "--save", "get-item")
        saved = json.loads((self.api_dir / "requests" / "get-item.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["path"], "/items/{{itemId}}")

    def test_save_name_cannot_escape_the_requests_dir(self):
        for name in ("../evil", "/abs/evil", "a/../../evil"):
            result = self.cli("send", "GET", "/ping", "--save", name)
            self.assertEqual(result.returncode, 2, name)
            self.assertIn("Invalid --save name", result.stderr)
        self.assertFalse((self.api_dir / "evil.json").exists())

    def test_save_warns_about_a_fixed_secret_header(self):
        out = self.ok("send", "GET", "/ping", "--header", "X-Api-Key: literalvalue", "--save", "leaky").stdout
        self.assertIn("WARNING: headers.X-Api-Key", out)

    def test_list_and_show(self):
        self.ok("send", "GET", "/ping", "--save", "catalogs/one")
        listing = self.ok("list").stdout
        for piece in ("catalogs/one", "GET", "/ping", "[apikey]"):
            self.assertIn(piece, listing)
        self.assertIn('"path": "/ping"', self.ok("show", "catalogs/one").stdout)

    def test_list_with_nothing_saved(self):
        self.assertIn("no saved requests", self.ok("list").stdout)

    def test_run_unknown_request(self):
        result = self.cli("run", "nope")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)

    def test_run_by_relative_path(self):
        (self.root / "adhoc-file.json").write_text(json.dumps({"path": "/ping"}), encoding="utf-8")
        self.assertIn("→ 200", self.ok("run", "adhoc-file.json").stdout)

    def test_optional_query_variable_is_omitted_then_included(self):
        self.save_request("search", {"method": "GET", "path": "/echo",
                                     "query": {"upc": "{{upc}}", "page": "1"}})
        self.ok("run", "search")
        self.assertEqual(Handler.hits[-1], ("GET", "/api/echo?page=1"))
        self.ok("run", "search", "--var", "upc=012")
        self.assertEqual(Handler.hits[-1], ("GET", "/api/echo?upc=012&page=1"))

    def test_saved_request_with_a_missing_path_variable_is_refused(self):
        self.save_request("needs-id", {"path": "/items/{{itemId}}"})
        result = self.cli("run", "needs-id")
        self.assertEqual(result.returncode, 2)
        self.assertIn("itemId", result.stderr)
        self.assertEqual(Handler.hits, [])

    def test_request_files_in_the_legacy_shape_still_work(self):
        # Same shape as the requests the pre-plugin runner saved: name/method/path/query/body/capture,
        # no "auth" key, `{{var|default}}`, a `$[0]` capture and a null inside the body.
        self.save_request("items/latest", {"name": "Latest", "method": "GET", "path": "/echo",
                                             "query": {"count": "{{count|20}}"}})
        self.save_request("items/search", {"name": "Search", "method": "GET", "path": "/list",
                                             "query": {"upc": "{{upc}}", "page": "1"},
                                             "capture": {"firstId": "$[0].id"}})
        self.save_request("imports/bulk", {"name": "Import", "method": "POST", "path": "/items",
                                              "body": {"products": [{"externalId": "sku-1", "upc": "0123"},
                                                                    {"externalId": "sku-3", "upc": None}]}})
        listing = self.ok("list").stdout
        for name in ("items/latest", "items/search", "imports/bulk"):
            self.assertIn(name, listing)
        self.ok("run", "items/latest")
        self.assertEqual(Handler.hits[-1], ("GET", "/api/echo?count=20"))
        self.ok("run", "items/search")
        self.assertEqual(self.read_env()["vars"]["firstId"], "abc")
        self.assertIn('"upc": null', self.ok("run", "imports/bulk").stdout)


# ----------------------------------------------------------- e2e: env, history, root

class EnvHistoryTests(ServerCase):
    def test_env_show_masks_secrets_and_reports_the_base_url_source(self):
        out = self.ok("env", "show").stdout
        self.assertIn(f"baseUrl: {self.base}  [config.json]", out)
        self.assertIn("apiKey = ABCD…(20 chars)", out)
        self.assertNotIn(API_KEY, out)

    def test_env_set_variables_and_base_url(self):
        out = self.ok("env", "set", "tenantId=t-1", "baseUrl=http://localhost:9999/api").stdout
        self.assertIn("tenantId = t-1", out)
        self.assertIn("baseUrl: http://localhost:9999/api  [env.local.json]", out)
        env = self.read_env()
        self.assertEqual(env["baseUrl"], "http://localhost:9999/api")
        self.assertEqual(env["vars"]["tenantId"], "t-1")
        self.assertNotIn("baseUrl", env["vars"])

    def test_env_set_without_pairs_is_a_usage_error(self):
        self.assertEqual(self.cli("env", "set").returncode, 2)

    def test_env_set_rejects_a_pair_without_equals(self):
        self.assertEqual(self.cli("env", "set", "novalue").returncode, 2)

    def test_names_used_by_the_auth_map_are_masked_even_if_they_look_harmless(self):
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        config["auth"]["apikey"]["var"] = "myCred"
        self.write_config(config)
        self.write_env({"vars": {"myCred": "0123456789"}})
        self.assertIn("myCred = 0123…(10 chars)", self.ok("env", "show").stdout)

    @unittest.skipUnless(POSIX, "file modes are POSIX-only")
    def test_env_file_is_mode_600_after_a_write(self):
        (self.api_dir / "env.local.json").chmod(0o644)
        self.ok("env", "set", "a=b")
        self.assertEqual(stat.S_IMODE(os.stat(self.api_dir / "env.local.json").st_mode), 0o600)

    def test_history_shows_the_last_n_calls(self):
        self.ok("send", "GET", "/ping")
        self.ok("send", "GET", "/forbidden")
        one = self.ok("history", "-n", "1").stdout.strip().splitlines()
        self.assertEqual(len(one), 1)
        self.assertIn("403", one[0])
        self.assertIn("[adhoc]", one[0])
        self.assertEqual(len(self.ok("history").stdout.strip().splitlines()), 2)

    def test_history_when_empty(self):
        self.assertIn("no history", self.ok("history").stdout)

    def test_root_is_found_by_walking_up_from_a_subdirectory(self):
        sub = self.root / "a" / "b"
        sub.mkdir(parents=True)
        self.assertIn(self.base, self.ok("env", "show", root_flag=False, cwd=sub).stdout)

    def test_root_from_claude_project_dir(self):
        result = self.ok("env", "show", root_flag=False, cwd=tempfile.gettempdir(),
                         env={"CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertIn(self.base, result.stdout)

    def test_root_flag_is_accepted_after_the_command_too(self):
        result = self.ok("env", "show", "--root", str(self.root), root_flag=False, cwd=tempfile.gettempdir())
        self.assertIn(self.base, result.stdout)


# ---------------------------------------------------------------------- guardrails

class GuardrailTests(ProjectCase):
    REMOTE = "http://example.invalid/api"

    def test_remote_base_url_from_config_is_refused_without_allow_remote(self):
        self.write_config({"baseUrl": self.REMOTE, "defaultAuth": "none"})
        result = self.cli("send", "GET", "/ping")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not local", result.stderr)
        self.assertIn("--allow-remote", result.stderr)

    def test_remote_base_url_from_env_override_is_refused_too(self):
        self.write_config({"baseUrl": "http://localhost:1/api", "defaultAuth": "none"})
        self.write_env({"baseUrl": self.REMOTE, "vars": {}})
        self.assertEqual(self.cli("send", "GET", "/ping").returncode, 2)

    def test_saved_requests_are_guarded_too(self):
        self.write_config({"baseUrl": self.REMOTE, "defaultAuth": "none"})
        self.save_request("ping", {"path": "/ping"})
        result = self.cli("run", "ping")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not local", result.stderr)

    def test_local_hosts_come_from_config(self):
        self.write_config({"baseUrl": "http://localhost:1/api", "defaultAuth": "none", "localHosts": ["only-this"]})
        result = self.cli("send", "GET", "/ping")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not local", result.stderr)


# ---------------------------------------------------------------------------- init

class DetectStackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def touch(self, relative, text=""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_nothing_detected(self):
        self.assertIsNone(api.detect_stack(self.root))

    def test_functions_host(self):
        self.touch("src/My.Functions/host.json", "{}")
        self.touch("src/My.Functions/My.Functions.csproj", "<Project/>")
        found = api.detect_stack(self.root)
        self.assertEqual(found["stack"], "Azure Functions")
        self.assertEqual(found["baseUrl"], "http://localhost:7071/api")
        host = found["host"]
        self.assertEqual(host["start"][:3], ["func", "host", "start"])
        self.assertEqual(host["cwd"], "src/My.Functions")
        self.assertEqual(host["sourceGlobs"], ["src/**/*.cs"])
        self.assertIn("My.Functions.dll", host["processPatterns"])

    def test_functions_host_at_the_root_has_no_cwd(self):
        self.touch("host.json", "{}")
        self.assertNotIn("cwd", api.detect_stack(self.root)["host"])

    def test_dotnet_web_project_uses_the_launch_settings_url(self):
        self.touch("Api/Api.csproj", '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>')
        self.touch("Api/Properties/launchSettings.json",
                   json.dumps({"profiles": {"https": {"applicationUrl": "https://localhost:7001;http://localhost:5123"}}}))
        found = api.detect_stack(self.root)
        self.assertEqual(found["host"]["start"], ["dotnet", "run"])
        self.assertEqual(found["host"]["cwd"], "Api")
        self.assertEqual(found["baseUrl"], "http://localhost:5123")

    def test_dotnet_web_project_without_launch_settings(self):
        self.touch("Api.csproj", '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>')
        self.assertEqual(api.detect_stack(self.root)["baseUrl"], "http://localhost:5000")

    def test_non_web_csproj_is_ignored(self):
        self.touch("Lib/Lib.csproj", '<Project Sdk="Microsoft.NET.Sdk"></Project>')
        self.assertIsNone(api.detect_stack(self.root))

    def test_npm_dev_script(self):
        self.touch("package.json", json.dumps({"scripts": {"dev": "vite"}, "devDependencies": {"vite": "^5"}}))
        found = api.detect_stack(self.root)
        self.assertEqual(found["host"]["start"], ["npm", "run", "dev"])
        self.assertEqual(found["baseUrl"], "http://localhost:5173")
        self.assertNotIn("sourceGlobs", found["host"])

    def test_package_json_without_a_dev_script_is_ignored(self):
        self.touch("package.json", json.dumps({"scripts": {"build": "tsc"}}))
        self.assertIsNone(api.detect_stack(self.root))

    def test_functions_wins_over_npm(self):
        self.touch("host.json", "{}")
        self.touch("package.json", json.dumps({"scripts": {"dev": "x"}}))
        self.assertEqual(api.detect_stack(self.root)["stack"], "Azure Functions")

    def test_dependency_folders_are_not_searched(self):
        self.touch("node_modules/dep/package.json", json.dumps({"scripts": {"dev": "x"}}))
        self.assertIsNone(api.detect_stack(self.root))


class InitTests(ProjectCase):
    def test_creates_config_env_and_gitignore(self):
        result = self.cli("init")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["defaultAuth"], "none")
        self.assertEqual(config["localHosts"], ["localhost", "127.0.0.1", "::1"])
        self.assertIn("bearer", config["auth"])
        self.assertIsNone(config["auth"]["none"])
        self.assertNotIn("host", config)
        self.assertNotIn("seed", config)
        self.assertEqual(self.read_env(), {"vars": {}})
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8"),
                         ".claude/api/env.local.json\n.claude/api/.last/\n")
        self.assertIn("No stack detected", result.stdout)

    @unittest.skipUnless(POSIX, "file modes are POSIX-only")
    def test_env_file_is_mode_600(self):
        self.cli("init")
        self.assertEqual(stat.S_IMODE(os.stat(self.api_dir / "env.local.json").st_mode), 0o600)

    def test_gitignore_is_idempotent_and_keeps_existing_lines(self):
        (self.root / ".gitignore").write_text("bin", encoding="utf-8")  # no trailing newline
        self.cli("init")
        self.cli("init")
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8"),
                         "bin\n.claude/api/env.local.json\n.claude/api/.last/\n")

    def test_gitignore_only_adds_what_is_missing(self):
        (self.root / ".gitignore").write_text("/.claude/api/.last\n", encoding="utf-8")
        self.cli("init")
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8"),
                         "/.claude/api/.last\n.claude/api/env.local.json\n")

    def test_existing_config_is_not_overwritten_without_force(self):
        self.cli("init")
        custom = {"baseUrl": "http://localhost:1/x", "custom": True}
        self.write_config(custom)
        result = self.cli("init")
        self.assertEqual(result.returncode, 0)
        self.assertIn("kept", result.stdout)
        self.assertEqual(json.loads((self.api_dir / "config.json").read_text(encoding="utf-8")), custom)
        self.assertNotIn("No stack detected", result.stdout)

    def test_force_overwrites_the_config(self):
        self.write_config({"baseUrl": "http://localhost:1/x", "custom": True})
        self.assertEqual(self.cli("init", "--force").returncode, 0)
        self.assertNotIn("custom", json.loads((self.api_dir / "config.json").read_text(encoding="utf-8")))

    def test_legacy_api_dir_keeps_requests_and_env_byte_for_byte(self):
        request = self.api_dir / "requests" / "items" / "latest.json"
        request.parent.mkdir(parents=True)
        request.write_bytes(b'{"name":"Latest",  "method":"GET","path":"/v1/items/latest"}')
        env_bytes = b'{"baseUrl":  "http://localhost:7071/api", "vars": {"apiKey": "' + b"K" * 64 + b'"}}'
        (self.api_dir / "env.local.json").write_bytes(env_bytes)
        before = request.read_bytes()
        result = self.cli("init")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(request.read_bytes(), before)
        self.assertEqual((self.api_dir / "env.local.json").read_bytes(), env_bytes)
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["baseUrl"], "http://localhost:7071/api")
        self.assertEqual(config["defaultAuth"], "apikey")
        self.assertIn("preserved (1 saved request", result.stdout)
        self.assertNotIn("K" * 64, result.stdout)

    def test_proposes_a_host_from_the_detected_stack(self):
        (self.root / "package.json").write_text(json.dumps({"scripts": {"dev": "node server.js"}}), encoding="utf-8")
        result = self.cli("init")
        self.assertIn("Detected stack: Node (npm run dev)", result.stdout)
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["host"]["start"], ["npm", "run", "dev"])
        self.assertEqual(config["baseUrl"], "http://localhost:3000")

    def test_init_fails_clearly_when_the_given_root_does_not_exist(self):
        with tempfile.TemporaryDirectory() as bare:
            result = run_cli(bare, "init", "--root", str(Path(bare) / "missing"), root_flag=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)


# ---------------------------------------------------------------------------- host

@unittest.skipUnless(POSIX, "host restart is POSIX-first (Windows is best effort and not tested here)")
class HostTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.port = free_port()
        self.source = self.root / "src" / "app.txt"
        self.source.parent.mkdir()
        self.source.write_text("v1", encoding="utf-8")
        old = time.time() - 100
        os.utime(self.source, (old, old))
        self.write_config({
            "baseUrl": f"http://127.0.0.1:{self.port}", "defaultAuth": "none",
            "host": {
                "start": [sys.executable, "-u", "-m", "http.server", str(self.port), "--bind", "127.0.0.1"],
                "healthUrl": f"http://127.0.0.1:{self.port}/",
                "processPatterns": [f"http.server {self.port}"],
                "sourceGlobs": ["src/**/*.txt"], "sourceIgnore": ["**/ignored/**"],
                "startTimeoutSec": 30}})
        self.addCleanup(self.kill_host)

    def saved_pid(self):
        return json.loads((self.api_dir / ".last" / "host.json").read_text(encoding="utf-8"))["pid"]

    @staticmethod
    def kill_pid(pid):
        try:
            os.killpg(pid, 9)
        except OSError:
            pass

    def kill_host(self):
        try:
            self.kill_pid(self.saved_pid())
        except (OSError, ValueError, KeyError):
            pass

    def test_status_restart_logs_and_outdated_warning(self):
        self.assertIn("DOWN", self.cli("host", "status").stdout)

        restarted = self.cli("host", "restart")
        self.assertEqual(restarted.returncode, 0, restarted.stderr + restarted.stdout)
        self.assertIn("host responding", restarted.stdout)
        first_pid = self.saved_pid()
        self.assertTrue(api.process_alive(first_pid))

        status = self.cli("host", "status").stdout
        self.assertIn("responding", status)
        self.assertNotIn("OUTDATED", status)

        logs = self.cli("host", "logs", "-n", "5").stdout
        self.assertNotIn("(no log)", logs)
        self.assertTrue(logs.strip())

        future = time.time() + 30
        os.utime(self.source, (future, future))
        stale = self.cli("host", "status").stdout
        self.assertIn("OUTDATED", stale)
        self.assertIn("src/app.txt", stale)

        again = self.cli("host", "restart")
        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
        self.assertIn("stopped previous host process", again.stdout)
        self.assertFalse(api.process_alive(first_pid), "the previous host must be gone")
        self.assertNotEqual(self.saved_pid(), first_pid)

    def test_ignored_files_do_not_trigger_the_warning(self):
        self.assertEqual(self.cli("host", "restart").returncode, 0)
        ignored = self.root / "src" / "ignored" / "noise.txt"
        ignored.parent.mkdir()
        ignored.write_text("x", encoding="utf-8")
        future = time.time() + 30
        os.utime(ignored, (future, future))
        self.assertNotIn("OUTDATED", self.cli("host", "status").stdout)

    def test_without_source_globs_there_is_no_warning(self):
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        del config["host"]["sourceGlobs"]
        self.write_config(config)
        self.assertEqual(self.cli("host", "restart").returncode, 0)
        future = time.time() + 30
        os.utime(self.source, (future, future))
        self.assertNotIn("OUTDATED", self.cli("host", "status").stdout)

    def test_status_of_a_host_started_elsewhere(self):
        self.assertEqual(self.cli("host", "restart").returncode, 0)
        self.addCleanup(self.kill_pid, self.saved_pid())  # host.json is about to disappear
        (self.api_dir / ".last" / "host.json").unlink()
        self.assertIn("started outside this runner", self.cli("host", "status").stdout)

    def test_startup_failure_prints_the_log_tail(self):
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        config["host"]["start"] = [sys.executable, "-c", "print('boom on startup'); raise SystemExit(3)"]
        config["host"]["processPatterns"] = []
        self.write_config(config)
        result = self.cli("host", "restart")
        self.assertEqual(result.returncode, 2)
        self.assertIn("exited during startup (exit code 3)", result.stdout)
        self.assertIn("boom on startup", result.stdout)
        self.assertIn("ERRO:", result.stderr)

    def test_startup_timeout(self):
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        config["host"]["start"] = [sys.executable, "-c", "import time; time.sleep(30)"]
        config["host"]["processPatterns"] = []
        config["host"]["startTimeoutSec"] = 1
        self.write_config(config)
        result = self.cli("host", "restart")
        self.assertEqual(result.returncode, 2)
        self.assertIn("did not respond within 1 s", result.stderr)

    def test_unknown_start_command(self):
        config = json.loads((self.api_dir / "config.json").read_text(encoding="utf-8"))
        config["host"]["start"] = ["definitely-not-a-real-command-xyz"]
        self.write_config(config)
        result = self.cli("host", "restart")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)


class HostNotConfiguredTests(ProjectCase):
    def test_every_host_action_says_it_is_not_configured(self):
        self.write_config({"baseUrl": "http://localhost:1/api"})
        for action in ("status", "restart", "logs"):
            result = self.cli("host", action)
            self.assertEqual(result.returncode, 2, action)
            self.assertIn("not configured", result.stderr)
            self.assertIn("init", result.stderr)


# ---------------------------------------------------------------------------- seed

class SeedTests(ProjectCase):
    def setUp(self):
        super().setUp()
        self.write_config({"baseUrl": "http://localhost:1/api", "defaultAuth": "none",
                           "seed": {"command": [sys.executable, ".claude/api/seed.py"]}})
        self.write_env({"vars": {"keep": "me"}})

    def write_seed(self, code):
        (self.api_dir / "seed.py").write_text(code, encoding="utf-8")

    def test_output_is_merged_into_env_and_printed_masked(self):
        self.write_seed(
            "import json, sys\n"
            "print(json.dumps({'baseUrl': 'http://localhost:9000/api', 'vars': {"
            "'apiKey': 'SEEDKEY-0123456789', 'tenantId': 't-1', "
            "'rotated': 'yes' if '--rotate' in sys.argv else 'no'}}))\n")
        result = self.cli("seed")
        self.assertEqual(result.returncode, 0, result.stderr)
        env = self.read_env()
        self.assertEqual(env["baseUrl"], "http://localhost:9000/api")
        self.assertEqual(env["vars"], {"keep": "me", "apiKey": "SEEDKEY-0123456789", "tenantId": "t-1", "rotated": "no"})
        self.assertNotIn("SEEDKEY-0123456789", result.stdout)
        self.assertIn("SEED…(18 chars)", result.stdout)
        self.assertIn("merged 3 variable(s)", result.stdout)

    def test_rotate_is_forwarded_to_the_command(self):
        self.write_seed("import json, sys\nprint(json.dumps({'vars': {'rotated': '--rotate' in sys.argv}}))\n")
        self.assertEqual(self.cli("seed", "--rotate").returncode, 0)
        self.assertIs(self.read_env()["vars"]["rotated"], True)

    def test_the_command_runs_from_the_project_root(self):
        self.write_seed("import json, os\nprint(json.dumps({'vars': {'cwd': os.getcwd()}}))\n")
        self.assertEqual(self.cli("seed", cwd=self.api_dir).returncode, 0)
        self.assertEqual(Path(self.read_env()["vars"]["cwd"]).resolve(), self.root)

    def test_nonzero_exit_becomes_an_error_with_the_stderr(self):
        self.write_seed("import sys\nsys.stderr.write('db unreachable')\nsys.exit(4)\n")
        result = self.cli("seed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("exit 4", result.stderr)
        self.assertIn("db unreachable", result.stderr)
        self.assertEqual(self.read_env(), {"vars": {"keep": "me"}})

    def test_output_that_is_not_json_is_an_error_and_is_not_echoed(self):
        self.write_seed("print('hello secret-looking-thing')\n")
        result = self.cli("seed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must print a JSON object", result.stderr)
        self.assertNotIn("secret-looking-thing", result.stderr)

    def test_not_configured_explains_how_to_configure(self):
        self.write_config({"baseUrl": "http://localhost:1/api"})
        result = self.cli("seed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("seed is not configured", result.stderr)
        self.assertIn('"command"', result.stderr)
        self.assertIn("stdout", result.stderr)

    def test_never_runs_against_a_remote_target(self):
        marker = self.root / "ran.txt"
        self.write_seed(f"open({str(marker)!r}, 'w').close()\nprint('{{}}')\n")
        self.write_config({"baseUrl": "http://example.invalid/api", "defaultAuth": "none",
                           "seed": {"command": [sys.executable, ".claude/api/seed.py"]}})
        result = self.cli("seed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("seed refused", result.stderr)
        self.assertFalse(marker.exists(), "the seed command must not even start")

    def test_a_remote_base_url_returned_by_the_command_is_refused(self):
        self.write_seed("import json\nprint(json.dumps({'baseUrl': 'http://example.invalid/api', 'vars': {'a': 'b'}}))\n")
        result = self.cli("seed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-local", result.stderr)
        self.assertEqual(self.read_env(), {"vars": {"keep": "me"}})


if __name__ == "__main__":
    unittest.main()
