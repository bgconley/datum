import os
import stat
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

WRAPPER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "adapters", "codex", "datum-codex-wrapper.sh"
)

ADAPTERS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "adapters", "codex"
)


def test_wrapper_exists_and_is_executable():
    assert os.path.exists(WRAPPER_PATH)
    assert os.stat(WRAPPER_PATH).st_mode & stat.S_IXUSR


def test_agents_template_exists():
    path = os.path.join(ADAPTERS_DIR, "AGENTS.md.template")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "get_project_context" in content
    assert "search_project_memory" in content
    assert "{{PROJECT_SLUG}}" in content


class _LifecycleMockHandler(BaseHTTPRequestHandler):
    enforcement_mode = "advisory"
    fail_flush = False
    fail_finalize = False
    calls: list[str] = []

    def _send_json(self, status: int, body: str = "{}") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        cls = type(self)
        cls.calls.append(f"GET {self.path}")
        if self.path.startswith("/api/v1/projects/") and "/context" in self.path:
            self._send_json(200, '{"ok": true}')
            return
        if self.path.startswith("/api/v1/agent/sessions/") and self.path.endswith("/status"):
            self._send_json(200, f'{{"enforcement_mode":"{cls.enforcement_mode}"}}')
            return
        self._send_json(404, '{"detail":"not found"}')

    def do_POST(self) -> None:
        cls = type(self)
        cls.calls.append(f"POST {self.path}")
        if self.path == "/api/v1/agent/sessions/start":
            self._send_json(201, '{"started": true}')
            return
        if self.path.endswith("/flush"):
            if cls.fail_flush:
                self._send_json(500, '{"detail":"flush failed"}')
            else:
                self._send_json(200, '{"flushed": true}')
            return
        if self.path.endswith("/finalize"):
            if cls.fail_finalize:
                self._send_json(500, '{"detail":"finalize failed"}')
            else:
                self._send_json(200, '{"finalized": true}')
            return
        self._send_json(404, '{"detail":"not found"}')

    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def _mock_lifecycle_server(
    *,
    enforcement_mode: str,
    fail_flush: bool = False,
    fail_finalize: bool = False,
):
    handler = type(
        "LifecycleHandler",
        (_LifecycleMockHandler,),
        {
            "enforcement_mode": enforcement_mode,
            "fail_flush": fail_flush,
            "fail_finalize": fail_finalize,
            "calls": [],
        },
    )
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        yield f"http://127.0.0.1:{port}/api/v1", handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _run_wrapper(tmp_path, api_base: str) -> subprocess.CompletedProcess[str]:
    fake_codex = tmp_path / "codex"
    fake_codex.write_text(
        "#!/usr/bin/env bash\nexit ${CODEX_TEST_EXIT_CODE:-0}\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env["DATUM_API"] = api_base
    env["DATUM_PROJECT_SLUG"] = "test-project"
    env["DATUM_SESSION_ID"] = "ses_codex_wrapper_test"
    env["DATUM_API_KEY"] = "test-key"

    return subprocess.run(
        ["bash", WRAPPER_PATH],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_wrapper_fails_postflight_in_blocking_mode(tmp_path):
    with _mock_lifecycle_server(
        enforcement_mode="blocking",
        fail_flush=True,
    ) as (api_base, handler):
        result = _run_wrapper(tmp_path, api_base)

    assert result.returncode == 65
    assert "ERROR: could not flush deltas" in result.stdout
    assert "strict mode (blocking)" in result.stdout
    assert any(call.endswith("/flush") for call in handler.calls)
    assert any(call.endswith("/finalize") for call in handler.calls)


def test_wrapper_warns_but_exits_cleanly_in_advisory_mode(tmp_path):
    with _mock_lifecycle_server(
        enforcement_mode="advisory",
        fail_flush=True,
        fail_finalize=True,
    ) as (api_base, handler):
        result = _run_wrapper(tmp_path, api_base)

    assert result.returncode == 0
    assert "ERROR: could not flush deltas" in result.stdout
    assert "ERROR: could not finalize session" in result.stdout
    assert any(call.endswith("/flush") for call in handler.calls)
    assert any(call.endswith("/finalize") for call in handler.calls)
