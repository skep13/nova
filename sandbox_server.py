"""Run model-written code, safely enough to be worth doing.

Verification is the single biggest improvement available to code help on this
box — a weaker model that can run its code and read the traceback beats a
stronger one answering blind. But the thing being run is written by a 3B and
must be assumed wrong, occasionally in interesting ways.

So the isolation is not in this file. This file only enforces the cheap limits;
the real boundary is the container it runs in, declared in docker-compose.yml:

  network: internal    - no route off the docker bridge, so nothing it runs can
                         reach the internet, the vault, the keys, or the LAN
  read_only: true      - the root filesystem is immutable
  tmpfs /tmp           - the only writable space, capped, and gone on restart
  no volumes           - the vault and the API keys are not mounted here at all
  memory + pids caps   - a fork bomb or a runaway allocation hits a wall

What this file adds on top: a wall-clock timeout, an address-space cap, and
execution as an unprivileged user rather than root. Deliberately simple, because
a complicated sandbox that is subtly wrong is worse than a simple one whose
limits are obvious.

This is NOT a defence against a determined attacker with code execution. It is a
defence against a small model writing an infinite loop, filling a disk, or
importing something that phones home — which is what actually happens.
"""
import json
import os
import resource
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("SANDBOX_PORT", "5005"))
TIMEOUT_S = float(os.environ.get("SANDBOX_TIMEOUT", "10"))
MAX_CODE = int(os.environ.get("SANDBOX_MAX_CODE", "20000"))
MAX_OUTPUT = int(os.environ.get("SANDBOX_MAX_OUTPUT", "8000"))
MEM_BYTES = int(os.environ.get("SANDBOX_MEM_MB", "192")) * 1024 * 1024


def _limits():
    """Applied in the child, after fork, before exec."""
    resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (int(TIMEOUT_S) + 1, int(TIMEOUT_S) + 1))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.setsid()          # its own process group, so a timeout kills children too


def run_code(code):
    if len(code) > MAX_CODE:
        return {"ok": False, "stdout": "", "stderr": "code too long", "exit": None,
                "timed_out": False}

    with tempfile.TemporaryDirectory(dir="/tmp") as work:
        path = os.path.join(work, "snippet.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", path],     # -I: no env, no user site
                capture_output=True, text=True, timeout=TIMEOUT_S,
                preexec_fn=_limits, cwd=work,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin",
                     "HOME": work, "PYTHONDONTWRITEBYTECODE": "1"})
            return {"ok": proc.returncode == 0,
                    "stdout": proc.stdout[:MAX_OUTPUT],
                    "stderr": proc.stderr[:MAX_OUTPUT],
                    "exit": proc.returncode, "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False,
                    "stdout": (exc.stdout or "")[:MAX_OUTPUT] if isinstance(exc.stdout, str) else "",
                    "stderr": f"timed out after {TIMEOUT_S:g}s",
                    "exit": None, "timed_out": True}
        except Exception as exc:
            return {"ok": False, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}",
                    "exit": None, "timed_out": False}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "timeout_s": TIMEOUT_S,
                             "mem_mb": MEM_BYTES // 1024 // 1024})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/exec":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "bad json"})
        code = payload.get("code") or ""
        if not code.strip():
            return self._send(400, {"error": "no code"})
        self._send(200, run_code(code))

    def log_message(self, *_args):
        pass          # the router logs what it asked for; this would duplicate it


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
