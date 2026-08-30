"""Exercise every feature Nova has, and report what actually works.

Written because this system has now had several failures that were invisible
until someone reached for the thing: whisper crash-looping while docker
reported it Up, a nightly backup that had not run for a week, an endpoint that
405'd because nginx was never told about it, a microphone that stopped
listening a second after it started.

Each of those was findable in seconds by asking the system a real question.
None of them was found that way, because nothing asked.

So the tests check BEHAVIOUR, not status codes. A 200 from /recall proves the
router is up; it does not prove the right note came back. Where a correct
answer is knowable, it is asserted.

    python3 test_nova.py            # everything
    python3 test_nova.py --quick    # skip the slow generative ones

Exit code is the number of failures, so it can gate a deploy.
"""
import json
import subprocess
import sys
import time
import urllib.parse

BASE = "http://127.0.0.1:8080"
QUICK = "--quick" in sys.argv

results = []


def check(group, name, fn, slow=False):
    if slow and QUICK:
        results.append((group, name, None, "skipped"))
        return
    started = time.time()
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, f"{type(exc).__name__}: {str(exc)[:120]}"
    results.append((group, name, bool(ok), f"{detail}  [{time.time()-started:.1f}s]"))


def curl(path, method="GET", data=None, form=None, timeout=30, raw=False):
    cmd = ["curl", "-s", "-m", str(timeout), "-X", method, BASE + path]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    for k, v in (form or {}):
        cmd += ["-F", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    return out if raw else out


def code_of(path, method="GET", data=None, timeout=30, extra=None):
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-m", str(timeout), "-X", method, BASE + path]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd += extra or []
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def jget(path, timeout=30):
    return json.loads(curl(path, timeout=timeout))


def recall(q, timeout=40):
    out = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "--get", "--data-urlencode", f"q={q}",
         BASE + "/recall"], capture_output=True, text=True).stdout
    return json.loads(out)


def sse(path, body, timeout=900):
    out = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "-N", "-X", "POST", BASE + path,
         "-H", "Content-Type: application/json", "-d", json.dumps(body)],
        capture_output=True, text=True).stdout
    events, text = [], ""
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
        events.append(d)
        try:
            text += d["choices"][0]["delta"].get("content", "") or ""
        except Exception:
            pass
    return events, text


# --------------------------------------------------------------- the page ---
def t_page():
    return code_of("/") == "200", "the page is served"


def t_manifest():
    m = jget("/manifest.json")
    return m.get("name") == "Nova" and m.get("orientation") == "landscape", \
        f"name={m.get('name')} orientation={m.get('orientation')}"


def t_icons():
    codes = [code_of(p) for p in ("/icon-192.png", "/icon-512.png",
                                  "/apple-touch-icon.png")]
    return all(c == "200" for c in codes), f"icons {codes}"


def t_font_cache():
    out = subprocess.run(["curl", "-sI", "-m", "20", BASE + "/fonts/plex-mono-400.woff2"],
                         capture_output=True, text=True).stdout.lower()
    return "immutable" in out, "fonts served with a long cache header"


def t_avatar_404():
    # Must 404, not fall through to the page: the loader probes for artwork and
    # a 200 would have it decoding a 140 KB HTML document.
    return code_of("/avatar/default.png") == "404", "missing artwork 404s"


def t_no_emoji():
    page = curl("/", timeout=30)
    import unicodedata
    bad = [c for c in page if ord(c) > 0x2000 and (
        unicodedata.category(c) in ("So", "Sk")
        or 0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF)]
    return not bad, f"{len(bad)} pictographs in the served page"


# --------------------------------------------------------------- the model ---
def t_chat_local():
    # A nonce, because the recall cache replays a previously-cached HOSTED
    # answer on the local path when the question matches. That is deliberate
    # behaviour and it made this test report gpt-oss-120b for agent=local.
    nonce = str(int(time.time()))
    out = json.loads(curl("/v1/chat/completions", "POST",
                          {"messages": [{"role": "user",
                                         "content": f"Reply with the word alive. Ignore this: {nonce}"}],
                           "max_tokens": 10, "agent": "local"}, timeout=180))
    txt = out["choices"][0]["message"]["content"]
    model = out.get("model", "")
    return "alive" in txt.lower() and "Qwen2.5-3B" in model, f"{model.split('/')[-1]} said {txt.strip()[:30]!r}"


def t_chat_hosted():
    out = json.loads(curl("/v1/chat/completions", "POST",
                          {"messages": [{"role": "user", "content": "Reply with the word: alive"}],
                           "max_tokens": 10, "agent": "fast"}, timeout=90))
    return "alive" in out["choices"][0]["message"]["content"].lower(), "hosted agent answered"


def t_agent_fallback():
    # An agent with no key must fall back to local rather than error.
    out = json.loads(curl("/v1/chat/completions", "POST",
                          {"messages": [{"role": "user", "content": "Reply with the word: alive"}],
                           "max_tokens": 10, "agent": "deep"}, timeout=180))
    return "choices" in out, "an unconfigured agent still answered"


def t_agents_list():
    a = jget("/agents")
    names = {x["name"] for x in a["agents"]}
    local = next(x for x in a["agents"] if x["name"] == "local")
    return "local" in names and local["available"], f"{len(names)} agents, local available"


# ------------------------------------------------------------- retrieval ---
def t_recall_lexical():
    h = recall("what is a semaphore").get("hit") or {}
    return h.get("title") == "Semaphore", f"got {h.get('title')!r}"


def t_recall_acronym():
    h = recall("what is tls").get("hit") or {}
    return "Transport Layer" in (h.get("title") or ""), f"got {h.get('title')!r}"


def t_recall_semantic():
    h = recall("what happens to your body at very high places").get("hit") or {}
    return h.get("title") == "Altitude sickness", f"got {h.get('title')!r} via {h.get('via','lexical')}"


def t_recall_no_hubs():
    # A hub is a list of links and must never be returned as an answer.
    for q in ("cryptography", "networking", "programming", "wellbeing"):
        h = recall(q).get("hit") or {}
        if (h.get("file") or "").startswith("moc-"):
            return False, f"{q!r} returned the hub {h.get('file')}"
    return True, "hubs stay out of retrieval"


def t_recall_source():
    # Identifiers are now indexed whole as well as split, so a function can be
    # asked for by its exact name. Both spellings are checked: an underscore
    # name from the router, and a camelCase one from the page.
    bad = []
    for q, want in (("how does search_vault score notes", "search_vault"),
                    ("what does gather_sources do", "gather_sources"),
                    ("what does demoteMode do", "demoteMode")):
        h = recall(q).get("hit") or {}
        if want not in (h.get("title") or ""):
            bad.append(f"{want}->{h.get('title')!r}")
    return not bad, "; ".join(bad) or "identifiers resolve by exact name"


def t_recall_new_domains():
    want = {"how do i deal with loneliness": "Loneliness",
            "what is a coral reef": "Coral reef",
            "what is occupational burnout": "Occupational burnout"}
    bad = []
    for q, expect in want.items():
        h = recall(q).get("hit") or {}
        if h.get("title") != expect:
            bad.append(f"{q!r}->{h.get('title')!r}")
    return not bad, "; ".join(bad) or "all three domains answer"


def t_recall_reference():
    """The hand-written cheatsheets, asked for the way a person asks.

    Each of these lost to an encyclopedia article at some point. Two separate
    causes: a title that did not carry the word anybody types, and a stemmer
    that split "certificates" from "certificate" so a title match scored as a
    body match. Neither failed loudly — retrieval returned a plausible article
    every time — so they are pinned here rather than trusted to stay fixed.
    """
    want = {"why is my certificate not trusted": "TLS",
            "how much water for rice": "Cooking ratios",
            "how do i make a virtual environment": "Python virtual environments",
            "how do i centre a div": "CSS flexbox",
            "what is iso 8601": "Date and time formats",
            "what port is postgres on": "Common network ports"}
    bad = []
    for q, expect in want.items():
        got = (recall(q).get("hit") or {}).get("title") or ""
        if not got.startswith(expect):
            bad.append(f"{q!r}->{got!r}")
    return not bad, "; ".join(bad) or f"{len(want)} reference lookups resolve"


def t_stem_plurals():
    """Singular and plural have to reach the same stem or they never meet.

    Measured at 13 of 20 common pairs failing, every one of them silently: the
    query still returned something, just the wrong thing. The four exceptions
    are short words held back by the length floor, which exists to stop
    over-stemming turning distinct words into each other.
    """
    pairs = [("certificate", "certificates"), ("package", "packages"),
             ("service", "services"), ("database", "databases"),
             ("interface", "interfaces"), ("device", "devices"),
             ("process", "processes"), ("address", "addresses"),
             ("branch", "branches"), ("cache", "caches"),
             ("watch", "watches"), ("class", "classes"),
             ("image", "images"), ("module", "modules"),
             ("value", "values"), ("table", "tables")]
    # Asked of the running container rather than through an HTTP endpoint.
    # _stem has no route and does not deserve one: adding a debug endpoint to
    # production so a test can reach an internal function is a worse trade than
    # this test knowing the container's name.
    words = sorted({w for pair in pairs for w in pair})
    script = ("import sys, json; sys.path.insert(0, '/app'); import remote_proxy as R;"
              f"print(json.dumps({{w: R._stem(w) for w in {words!r}}}))")
    out = subprocess.run(["docker", "exec", "orb-remote", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return False, "could not reach _stem in the container"
    stems = json.loads(out)
    bad = [f"{a}={stems.get(a)} {b}={stems.get(b)}"
           for a, b in pairs if stems.get(a) != stems.get(b)]
    return not bad, "; ".join(bad) or f"{len(pairs)} singular/plural pairs meet"


# -------------------------------------------------------------- research ---
def t_research_floor():
    return code_of("/research", "POST",
                   {"q": "blorp glimf wuzzle", "agent": "fast"}, timeout=120) == "404", \
        "nonsense is refused rather than written up"


def t_research_archive():
    evs, text = sse("/research", {"q": "what is a rainbow table", "agent": "fast"}, 300)
    note = next((e["orb_note"] for e in evs if "orb_note" in e), None)
    return bool(note and note.get("file")) and len(text) > 200, \
        f"{len(text)} chars, filed {(note or {}).get('file')}"


def t_research_web():
    evs, text = sse("/research", {"q": "what is the uv python package manager",
                                  "title": "uv test", "agent": "fast", "web": True}, 300)
    note = next((e["orb_note"] for e in evs if "orb_note" in e), None)
    web = any("web:" in s for s in (note or {}).get("sources", []))
    return bool(note) and web, f"sources: {len((note or {}).get('sources', []))}, web={web}"


# ----------------------------------------------------------------- health ---
def t_health():
    h = jget("/health", timeout=90)
    return h.get("state") == "ok", f"state={h.get('state')} failing={h.get('failing')}"


def t_health_backup():
    h = jget("/health", timeout=90)
    b = h["checks"].get("backup", {})
    return b.get("ok"), f"{b.get('age_hours')}h old, {b.get('notes')} notes"


def t_health_embeddings():
    h = jget("/health", timeout=90)
    e = h["checks"].get("embeddings", {})
    return e.get("ok") and e.get("vectors", 0) > 500, f"{e.get('vectors')} vectors"


# ------------------------------------------------------------ maintenance ---
def t_maint_list():
    m = jget("/maintain")
    return "restart" in m.get("actions", {}), f"{len(m.get('actions', {}))} actions allowed"


def t_maint_rejects_command():
    return code_of("/maintain", "POST", {"action": "rm -rf /"}, timeout=30) == "400", \
        "an arbitrary command is refused"


def t_maint_rejects_service():
    return code_of("/maintain", "POST",
                   {"action": "restart", "target": "; reboot"}, timeout=30) == "400", \
        "an injected service name is refused"


def t_maint_works():
    out = json.loads(curl("/maintain", "POST", {"action": "repair-links"}, timeout=180))
    return out.get("ok"), (out.get("message") or "")[:70]


# --------------------------------------------------------------- sandbox ---
def t_run_basic():
    out = json.loads(curl("/run", "POST", {"code": "print(6*7)"}, timeout=60))
    return out.get("ok") and out.get("stdout", "").strip() == "42", f"stdout={out.get('stdout','').strip()!r}"


def t_run_timeout():
    out = json.loads(curl("/run", "POST", {"code": "while True: pass"}, timeout=90))
    return out.get("timed_out"), f"stderr={out.get('stderr','')[:40]!r}"


def t_run_no_network():
    out = json.loads(curl("/run", "POST", {
        "code": "import urllib.request\nprint(urllib.request.urlopen('http://1.1.1.1',timeout=5).status)"},
        timeout=60))
    return not out.get("ok"), "network refused from inside the sandbox"


def t_run_no_vault():
    out = json.loads(curl("/run", "POST", {
        "code": "import os\nprint(os.path.exists('/mem'), os.path.exists('/run/keys'))"},
        timeout=60))
    return "False False" in (out.get("stdout") or ""), f"stdout={out.get('stdout','').strip()!r}"


def t_run_readonly():
    out = json.loads(curl("/run", "POST", {
        "code": "open('/probe','w').write('x')"}, timeout=60))
    return not out.get("ok"), "root filesystem is read-only"


def t_code_loop():
    evs, _ = sse("/code", {"q": "Print the sum of the first 10 positive integers.",
                           "agent": "fast"}, 600)
    done = next((e for e in evs if e.get("stage") == "done"), None)
    return bool(done and done.get("ok")) and "55" in (done or {}).get("stdout", ""), \
        f"ok={(done or {}).get('ok')} attempts={(done or {}).get('attempts')} out={(done or {}).get('stdout','').strip()[:20]!r}"


# ------------------------------------------------------------------ other ---
def t_place():
    p = jget("/place?lat=54.4544&lon=-3.2119", timeout=40)
    return bool(p.get("nearest")), f"nearest={str(p.get('nearest'))[:50]}"


def t_wiki():
    return code_of("/wiki/search?books.filter.lang=eng&pattern=hypothermia&userlang=en",
                   timeout=60) == "200", "the offline archive answers"


def t_tts_stt():
    n = subprocess.run(["curl", "-s", "-m", "60", "-X", "POST", BASE + "/tts",
                        "-H", "Content-Type: application/json",
                        # A whole sentence, because that is what a person says
                        # and because whisper uses the surrounding words. The
                        # bare fragment "grid reference" is transcribed as
                        # "create reference" every time; inside this sentence it
                        # is correct. Testing the fragment measured an input the
                        # interface never receives.
                        "-d", json.dumps({"text": "what is my grid reference"}),
                        "-o", "/tmp/_t.wav", "-w", "%{size_download}"],
                       capture_output=True, text=True).stdout
    if int(n or 0) < 1000:
        return False, f"tts produced {n} bytes"
    out = subprocess.run(["curl", "-s", "-m", "120", "-X", "POST", BASE + "/stt",
                          "-F", "file=@/tmp/_t.wav", "-F", "response_format=json"],
                         capture_output=True, text=True).stdout
    heard = json.loads(out).get("text", "").strip().lower()
    # No retry: whisper is deterministic, so the same audio gives the same
    # answer and a second attempt only measures the clock.
    return "grid reference" in heard, f"heard {heard!r}"


def t_webdav():
    c = code_of("/dav/Orb/", "PROPFIND", timeout=30, extra=["-H", "Depth: 1"])
    return c == "207", f"PROPFIND -> {c}"


def t_mem_store():
    return code_of("/mem/") == "200", "the short-fact store serves"


def t_ingest_rejects_empty():
    return code_of("/ingest", "POST", timeout=30) == "400", "an empty upload is refused"


def t_vault_links():
    import pathlib, re
    V = pathlib.Path("/opt/orb/mem")
    # Obsidian does not parse a wikilink inside a fenced block OR inside inline
    # backticks, so neither counts as a link. Stripping only fences reported the
    # markdown reference note as broken for documenting the syntax correctly —
    # the note was right and the check was wrong.
    fence = re.compile(r"```.*?```|`[^`\n]*`", re.S)
    stems = {p.stem for p in V.glob("*.md")}
    bad = 0
    for p in V.glob("*.md"):
        prose = fence.sub("", p.read_text(encoding="utf-8", errors="replace"))
        for t in set(re.findall(r"\[\[([^\]|#]+)", prose)):
            if t.strip() not in stems:
                bad += 1
    return bad == 0, f"{bad} broken links across {len(stems)} notes"


def t_vault_hubs():
    import pathlib, re
    V = pathlib.Path("/opt/orb/mem")
    hubs = list(V.glob("moc-*.md"))
    linked = set()
    for h in hubs:
        linked |= {m for m in re.findall(r"\[\[([^\]|#]+)", h.read_text(encoding="utf-8", errors="replace"))}
    notes = {p.stem for p in V.glob("*.md")
             if not p.stem.startswith(("moc-", "src-")) and p.stem != "index"}
    orphans = notes - linked
    return len(orphans) < 40, f"{len(hubs)} hubs, {len(orphans)} notes not in any hub"


GROUPS = [
    ("page", [("served", t_page, False), ("manifest", t_manifest, False),
              ("icons", t_icons, False), ("font caching", t_font_cache, False),
              ("missing avatar 404s", t_avatar_404, False),
              ("no pictographs", t_no_emoji, False)]),
    ("model", [("local chat", t_chat_local, True), ("hosted chat", t_chat_hosted, True),
               ("unconfigured agent falls back", t_agent_fallback, True),
               ("agent roster", t_agents_list, False)]),
    ("retrieval", [("lexical", t_recall_lexical, False), ("acronym alias", t_recall_acronym, False),
                   ("semantic fallback", t_recall_semantic, False),
                   ("hubs excluded", t_recall_no_hubs, False),
                   ("source code", t_recall_source, False),
                   ("new domains", t_recall_new_domains, False),
                   ("reference notes", t_recall_reference, False),
                   ("stem plurals", t_stem_plurals, False)]),
    ("research", [("relevance floor", t_research_floor, True),
                  ("from the archive", t_research_archive, True),
                  ("from the web", t_research_web, True)]),
    ("health", [("overall", t_health, False), ("backup freshness", t_health_backup, False),
                ("embeddings", t_health_embeddings, False)]),
    ("maintenance", [("allowlist published", t_maint_list, False),
                     ("refuses a command", t_maint_rejects_command, False),
                     ("refuses an injected service", t_maint_rejects_service, False),
                     ("performs an allowed action", t_maint_works, True)]),
    ("sandbox", [("executes", t_run_basic, False), ("stops an infinite loop", t_run_timeout, True),
                 ("no network", t_run_no_network, False),
                 ("no vault or keys", t_run_no_vault, False),
                 ("read-only root", t_run_readonly, False),
                 ("write-run-fix loop", t_code_loop, True)]),
    ("other", [("position", t_place, False), ("offline wikipedia", t_wiki, False),
               ("speech round trip", t_tts_stt, True), ("webdav", t_webdav, False),
               ("fact store", t_mem_store, False),
               ("ingest refuses empty", t_ingest_rejects_empty, False),
               ("vault links", t_vault_links, False),
               ("hub coverage", t_vault_hubs, False)]),
]


def main():
    for group, tests in GROUPS:
        for name, fn, slow in tests:
            check(group, name, fn, slow)

    last = None
    passed = failed = skipped = 0
    for group, name, ok, detail in results:
        if group != last:
            print(f"\n  {group.upper()}")
            last = group
        if ok is None:
            skipped += 1
            print(f"    SKIP  {name}")
        elif ok:
            passed += 1
            print(f"    pass  {name:34} {detail}")
        else:
            failed += 1
            print(f"    FAIL  {name:34} {detail}")

    print(f"\n  {passed} passed, {failed} failed, {skipped} skipped")
    return failed


if __name__ == "__main__":
    sys.exit(main())
