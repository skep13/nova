"""Fill the vault's blind spot: everything newer than the archive.

The offline Wikipedia was made once and cannot know what happened afterwards.
For most subjects that is fine — thermodynamics has not moved — but it is
exactly wrong for tooling, where a two-year-old answer is worse than no answer
because it is confidently obsolete.

So these come from the live web through /research, which searches, reads the
pages, and files the result with its source URLs and a web tag. Written as a
batch rather than asked one at a time, because the useful set is knowable in
advance and nobody wants to type thirty questions.

Runs inside LXC 101. Slow by design: each entry is a search, a few page fetches
and a generation. Use a hosted agent unless you have an afternoon.

    python3 build_web_notes.py            # hosted, the sensible default
    python3 build_web_notes.py local      # offline, roughly 3 minutes each
"""
import json
import subprocess
import sys
import time

BASE = "http://127.0.0.1:8080"

# (title for the note, question to research)
TOPICS = [
    ("uv (Python packaging)", "what is uv the python package and project manager and why is it used instead of pip"),
    ("Ruff (Python linter)", "what is ruff the python linter and formatter"),
    ("Polars", "what is polars the dataframe library and how does it compare to pandas"),
    ("DuckDB", "what is duckdb and what is it used for"),
    ("FastAPI", "what is fastapi and how does it compare to flask"),
    ("Pydantic", "what is pydantic used for and what changed in version 2"),
    ("httpx", "what is the httpx python library and how does it differ from requests"),
    ("Textual", "what is the textual python library for terminal user interfaces"),
    ("Rich (Python)", "what is the rich python library for terminal output"),
    ("Typer", "what is typer the python cli library"),
    ("pytest", "what is pytest and what are fixtures and parametrize used for"),
    ("SQLAlchemy 2.0", "what changed in sqlalchemy 2.0 and what is the modern query style"),
    ("PyTorch", "what is pytorch and what is it used for"),
    ("Hugging Face Transformers", "what is the hugging face transformers library"),
    ("llama.cpp", "what is llama.cpp and what does it do"),
    ("Ollama", "what is ollama and how does it differ from llama.cpp"),
    ("vLLM", "what is vllm and what is continuous batching"),
    ("GGUF", "what is the gguf file format and what are quantisation levels like Q4_K_M"),
    ("Vite", "what is vite the frontend build tool"),
    ("Bun", "what is bun the javascript runtime"),
    ("Deno", "what is deno and how does it differ from node.js"),
    ("htmx", "what is htmx and what problem does it solve"),
    ("Tailwind CSS", "what is tailwind css and how does utility-first styling work"),
    ("TypeScript", "what is typescript and what does it add to javascript"),
    ("Podman", "what is podman and how does it differ from docker"),
    ("Caddy", "what is the caddy web server and how does it handle https"),
    ("Traefik", "what is traefik the reverse proxy"),
    ("Prometheus and Grafana", "what are prometheus and grafana used for together"),
    ("Ansible", "what is ansible and what is a playbook"),
    ("OpenTofu", "what is opentofu and how does it relate to terraform"),
    ("Apache Parquet", "what is the parquet file format and why is it columnar"),
    ("Apache Arrow", "what is apache arrow and what problem does it solve"),
    ("SQLite", "what is sqlite and when should it be used instead of a server database"),
    ("PostgreSQL", "what is postgresql and what are its distinctive features"),
    ("Model Context Protocol", "what is the model context protocol for AI tools"),
]


def research(title, question, agent):
    body = json.dumps({"q": question, "title": title, "agent": agent, "web": True})
    out = subprocess.run(
        ["curl", "-s", "-m", "900", "-N", "-X", "POST", BASE + "/research",
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, text=True).stdout

    note, chars = None, 0
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        blob = line[5:].strip()
        if not blob or blob == "[DONE]":
            continue
        try:
            d = json.loads(blob)
        except Exception:
            continue
        if "orb_note" in d:
            note = d["orb_note"]
        try:
            chars += len(d["choices"][0]["delta"].get("content", "") or "")
        except Exception:
            pass
    return note, chars


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else "fast"
    ok = failed = 0
    started = time.time()

    for title, question in TOPICS:
        t = time.time()
        try:
            note, chars = research(title, question, agent)
        except Exception as exc:
            note, chars = None, 0
            print(f"  ERR  {title[:34]:36} {type(exc).__name__}")
        if note and note.get("file"):
            ok += 1
            srcs = len(note.get("sources") or [])
            print(f"  ok   {title[:34]:36} {chars:5} chars, {srcs} sources, {time.time()-t:5.1f}s")
        else:
            failed += 1
            print(f"  MISS {title[:34]:36} nothing filed ({time.time()-t:.0f}s)")

    print(f"\n  {ok} written, {failed} failed, {(time.time()-started)/60:.1f} minutes")
    print("  now run: python3 fix_links.py && python3 build_mocs.py")


main()
