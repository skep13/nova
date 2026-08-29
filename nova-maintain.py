"""Maintenance actions, executed outside the container that requests them.

Nova is allowed to restart its own services and rebuild its own indexes. It is
not allowed to run commands. Those are different powers and the difference is
the whole design here.

WHY THIS IS A SEPARATE PROCESS. The obvious implementation is to mount
/var/run/docker.sock into the router and call the Docker API from there. That
would work, and it would also mean any bug in a service reachable from the
browser is equivalent to root on this host, because control of the Docker
daemon is control of the machine. So the router gets no socket. It writes a
request to a file in the logs directory it already has, and this watcher — a
systemd service in the LXC, outside every container — decides whether that
request is one of the things Nova may do.

The trust boundary is therefore: a fully compromised router can ask for any
action on THIS list and nothing else. No path, no argument and no string from
the request ever reaches a shell; the service name is matched against a fixed
tuple and the command is built from constants.

Deliberately NOT on the list:

  Backups. The script lives on the Proxmox host and uses pct to reach into this
  container; the container cannot invoke it, and giving it a route to the
  hypervisor would undo the point of the boundary above. /health already
  reports backup age, which is the part that needs to be visible.

  Anything that writes code, changes config, or restarts the watcher itself.
"""
import json
import pathlib
import subprocess
import time

LOGS = pathlib.Path("/opt/orb/logs")
REQUEST = LOGS / "maintenance-request.json"
RESULT = LOGS / "maintenance-result.json"
ORB = pathlib.Path("/opt/orb")

POLL_S = 3
# A request older than this is ignored rather than run. Stops a queued action
# firing minutes later, long after whoever asked has given up and moved on.
STALE_S = 90

SERVICES = ("llama", "embed", "piper", "whisper", "kiwix", "webdav", "web",
            "remote", "searxng")


def compose(*args):
    return ["docker", "compose", "-f", str(ORB / "docker-compose.yml"), *args]


def act_restart(target):
    if target not in SERVICES:
        return False, f"{target!r} is not a service. Known: {', '.join(SERVICES)}"
    r = subprocess.run(compose("restart", target), capture_output=True,
                       text=True, timeout=180)
    ok = r.returncode == 0
    return ok, (f"restarted {target}" if ok else (r.stderr or r.stdout)[:300])


def act_reload_web(_):
    # Config test first: a reload with a broken config leaves nginx serving the
    # old one, but the error is then only visible in a log nobody reads.
    t = subprocess.run(["docker", "exec", "orb-web", "nginx", "-t"],
                       capture_output=True, text=True, timeout=60)
    if t.returncode != 0:
        return False, "nginx config test failed: " + (t.stderr or t.stdout)[:250]
    r = subprocess.run(["docker", "exec", "orb-web", "nginx", "-s", "reload"],
                       capture_output=True, text=True, timeout=60)
    ok = r.returncode == 0
    return ok, ("nginx reloaded" if ok else (r.stderr or r.stdout)[:300])


def act_rebuild_hubs(_):
    r = subprocess.run(["python3", str(ORB / "build_mocs.py")],
                       capture_output=True, text=True, timeout=300)
    ok = r.returncode == 0
    return ok, (r.stdout.strip().splitlines()[0] if ok and r.stdout.strip()
                else (r.stderr or "rebuilt")[:300])


def act_repair_links(_):
    r = subprocess.run(["python3", str(ORB / "fix_links.py")],
                       capture_output=True, text=True, timeout=300)
    ok = r.returncode == 0
    return ok, (" / ".join(l.strip() for l in r.stdout.strip().splitlines()[:3])
                if ok else (r.stderr or "failed")[:300])


def act_reindex(_):
    """Drop the embedding cache and let the router rebuild it."""
    try:
        (LOGS / "embeddings.json").unlink(missing_ok=True)
    except OSError as exc:
        return False, f"could not clear the cache: {exc}"
    r = subprocess.run(compose("restart", "remote"), capture_output=True,
                       text=True, timeout=180)
    ok = r.returncode == 0
    return ok, ("embedding cache cleared; rebuilding in the background"
                if ok else (r.stderr or r.stdout)[:300])


ACTIONS = {
    "restart": act_restart,
    "reload-web": act_reload_web,
    "rebuild-hubs": act_rebuild_hubs,
    "repair-links": act_repair_links,
    "reindex": act_reindex,
}


def write_result(req_id, ok, message, action=None, target=None):
    RESULT.write_text(json.dumps({
        "id": req_id, "ok": ok, "message": message,
        "action": action, "target": target,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }), encoding="utf-8")


def handle(req):
    req_id = str(req.get("id", ""))[:64]
    action = str(req.get("action", ""))[:32]
    target = str(req.get("target", ""))[:32]

    fn = ACTIONS.get(action)
    if not fn:
        write_result(req_id, False,
                     f"{action!r} is not an allowed action. Allowed: "
                     + ", ".join(sorted(ACTIONS)), action, target)
        return
    try:
        ok, message = fn(target)
    except subprocess.TimeoutExpired:
        ok, message = False, "timed out"
    except Exception as exc:
        ok, message = False, f"{type(exc).__name__}: {str(exc)[:200]}"
    write_result(req_id, ok, message, action, target)


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            if REQUEST.exists():
                raw = REQUEST.read_text(encoding="utf-8")
                # Consumed before it is run: a request that crashes this loop
                # must not be retried forever on every restart.
                REQUEST.unlink(missing_ok=True)
                try:
                    req = json.loads(raw)
                except Exception:
                    write_result("", False, "unreadable request")
                    req = None
                if req is not None:
                    age = time.time() - float(req.get("at", 0) or 0)
                    if age > STALE_S:
                        write_result(str(req.get("id", ""))[:64], False,
                                     f"ignored: request was {int(age)}s old")
                    else:
                        handle(req)
        except Exception:
            pass                      # the watcher must outlive any single request
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
