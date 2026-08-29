"""Put Nova's own source code in Nova's vault, so it can be retrieved.

The hand-written nova-*.md notes describe how this system works. They are prose,
and prose about code goes stale the moment the code changes. This puts the code
itself in the vault, so "how does search_vault decide" is answered with the
function rather than with a paragraph someone wrote about the function.

Split per top-level definition rather than per file. remote_proxy.py is two
thousand lines; as one note the retrieval excerpt lands 900 characters into
whatever happened to match first, which is usually the wrong function. One note
per def or class means the match IS the unit, and the note is the whole thing.

Tagged source so they are distinguishable from prose, and titled with the file
and symbol so the trace line says exactly what was retrieved.

Re-runnable: it deletes the source notes it wrote before regenerating, so a
renamed function does not leave a ghost behind.
"""
import datetime
import pathlib
import re

ORB = pathlib.Path("/opt/orb")
MEM = ORB / "mem"
NOW = datetime.datetime.now().isoformat(timespec="seconds")

# The files that ARE Nova. Excludes the generators, which are build tooling
# rather than the running system, and anything with a secret in it.
FILES = [
    ("remote_proxy.py", "python", "the agent router, retrieval, research, health"),
    ("nova-maintain.py", "python", "the maintenance watcher, outside the containers"),
    ("sandbox_server.py", "python", "the code sandbox"),
    ("nginx.conf", "nginx", "routing: which path reaches which container"),
    ("docker-compose.yml", "yaml", "the services, their limits and their networks"),
    ("orb-backup.sh", "shell", "the nightly backup, on the Proxmox host"),
]

# A top-level def/class in Python; a location block in nginx; a service in
# compose. Each is the natural unit someone would ask about.
PY_SPLIT = re.compile(r"^(?=(?:async\s+def|def|class)\s+\w+)", re.M)
NGINX_SPLIT = re.compile(r"^(?=\s*location\s)", re.M)
YAML_SPLIT = re.compile(r"^(?=  \w[\w-]*:\s*$)", re.M)

MAX_CHUNK = 7000        # a very long function is still one note, just a big one


def chunks(text, kind):
    if kind == "python":
        parts = PY_SPLIT.split(text)
    elif kind == "nginx":
        parts = NGINX_SPLIT.split(text)
    elif kind == "yaml":
        parts = YAML_SPLIT.split(text)
    else:
        parts = [text]
    return [p for p in parts if p.strip()]


def name_of(chunk, kind, index):
    if kind == "python":
        m = re.match(r"(?:async\s+def|def|class)\s+(\w+)", chunk.strip())
        if m:
            return m.group(1)
    elif kind == "nginx":
        m = re.search(r"location\s+(=\s*)?(\S+)", chunk)
        if m:
            return m.group(2).strip("{ ")
    elif kind == "yaml":
        m = re.match(r"\s*([\w-]+):", chunk.strip())
        if m:
            return m.group(1)
    return f"part-{index}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def main():
    for old in MEM.glob("src-*.md"):
        old.unlink()

    written = skipped = 0
    for fname, kind, purpose in FILES:
        path = ORB / fname
        if not path.exists():
            print(f"  missing, skipped: {fname}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")

        for i, chunk in enumerate(chunks(text, kind)):
            body = chunk.rstrip()
            if len(body) < 120:
                skipped += 1
                continue                      # imports, stray constants
            if len(body) > MAX_CHUNK:
                body = body[:MAX_CHUNK] + "\n\n... truncated ...\n"

            sym = name_of(chunk, kind, i)
            title = f"{fname}: {sym}"
            fence = "python" if kind == "python" else kind

            doc = ("---\n"
                   f"created: {NOW}\n"
                   f"title: {title}\n"
                   "tags: [source, nova]\n"
                   f"source: {fname}\n"
                   "---\n\n"
                   f"# {title}\n\n"
                   f"From {fname} — {purpose}.\n\n"
                   f"```{fence}\n{body}\n```\n")
            (MEM / f"src-{slug(fname)}-{slug(sym)}.md").write_text(doc, encoding="utf-8")
            written += 1

    print(f"  source notes written: {written}")
    print(f"  fragments too small to be worth a note: {skipped}")


main()
