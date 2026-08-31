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
import datetime
import json
import pathlib
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
    # None is preserved, not coerced: a test may report not-applicable, which
    # is neither a pass nor a failure. An engine that rate-limited us is not a
    # defect in Nova, and counting it as one teaches everybody to ignore red.
    results.append((group, name, None if ok is None else bool(ok),
                    f"{detail}  [{time.time()-started:.1f}s]"))


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


def jpost(path, body, timeout=60):
    out = curl(path, "POST", data=body, timeout=timeout)
    try:
        return json.loads(out)
    except Exception:
        return None


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


# ------------------------------------------------------------------ nova ---
def t_persona_no_drift():
    """The page's persona and the server's must be the same personality.

    They are two copies of the same ~2 KB of prompt: the browser assembles its
    own turn, and nova_turn assembles one for every other caller. Nothing stops
    someone editing one and not the other, and the failure is invisible — Nova
    simply sounds slightly different over the bridge than she does on the wrist,
    and no error is ever raised. So it is asserted rather than hoped for.
    """
    sys.path.insert(0, "/opt/orb")
    try:
        import extract_persona
        import persona
    except Exception as exc:
        return False, f"cannot import: {type(exc).__name__}: {exc}"

    html = open("/opt/orb/index.html", encoding="utf-8").read()
    blocks, fewshot = extract_persona.parse(html)
    bad = [n for n in extract_persona.BLOCKS if getattr(persona, n, None) != blocks[n]]
    if persona.FEWSHOT != fewshot:
        bad.append(f"FEWSHOT ({len(persona.FEWSHOT)} vs {len(fewshot)} turns)")
    return not bad, ("drifted: " + ", ".join(bad)) if bad else \
        f"{len(extract_persona.BLOCKS)} blocks + {len(fewshot)} turns identical"


def t_ask():
    """A whole turn through /ask: character, vault lookup and an answer.

    Asserts the vault was actually consulted, not just that a reply came back.
    A model this size will answer chmod from its own weights and sound
    confident doing it, so a plausible answer proves nothing about retrieval.
    """
    out = jpost("/ask", {"q": "what does chmod 600 mean"}, timeout=280)
    if not out:
        return False, "no response"
    answer = (out.get("answer") or "").strip()
    if not answer:
        return False, f"empty answer (agent={out.get('agent')})"
    if out.get("source") != "chmod and Unix file permissions":
        return False, f"wrong note attached: {out.get('source')!r}"
    return True, f"{len(answer)} chars, grounded in {out['source']!r}"


def t_ask_history():
    """Follow-up questions need the previous turns or they are unanswerable.

    "and for a directory?" means nothing on its own. If history were dropped,
    the reply would still be fluent and would be about something else entirely,
    which is the failure mode worth catching.
    """
    out = jpost("/ask", {
        "q": "and what about 644?",
        "history": [{"role": "user", "content": "what does chmod 600 mean"},
                    {"role": "assistant",
                     "content": "It sets a file readable and writable only by "
                                "its owner."}]}, timeout=280)
    if not out:
        return False, "no response"
    answer = (out.get("answer") or "").lower()
    # 644 is owner read/write, everyone else read. Any correct answer says so.
    if not any(w in answer for w in ("read", "readable")):
        return False, f"did not follow the thread: {answer[:90]!r}"
    return True, f"followed up: {answer[:70]!r}"


def t_note_write():
    """Create, refuse to clobber, append. The three states a note can be in."""
    import random
    title = f"suite note {random.randint(10000, 99999)}"
    a = jpost("/note", {"title": title, "body": "- first"}, timeout=60) or {}
    if a.get("action") != "created":
        return False, f"create failed: {a}"
    # Overwriting silently is the failure that loses a note, and a lost note is
    # indistinguishable from one that was never written.
    b = code_of("/note", "POST", {"title": title, "body": "- clobber"}, timeout=60)
    c = jpost("/note", {"title": title, "body": "- second", "append": True},
              timeout=60) or {}
    subprocess.run(["rm", "-f", f"/opt/orb/mem/{a['file']}"], capture_output=True)
    if b != "409":
        return False, f"duplicate returned {b}, expected 409"
    if c.get("action") != "appended":
        return False, f"append failed: {c}"
    return True, "created, refused a clobber, appended"


def t_note_traversal():
    """A title is never a path.

    The note endpoint is reachable from Telegram, so its input comes from the
    open internet by way of a chat message. slug() reduces to [a-z0-9-] and the
    resolved path is checked to sit inside the vault; either alone would be a
    single point of failure.
    """
    attempts = ["../../etc/passwd", "/etc/shadow", "....//....//root/.ssh/id_rsa",
                "note/../../../tmp/escaped"]
    made = []
    for t in attempts:
        out = jpost("/note", {"title": t, "body": "x"}, timeout=60) or {}
        if out.get("file"):
            made.append(out["file"])
    escaped = [f for f in ("/etc/passwd.md", "/etc/shadow.md", "/tmp/escaped.md")
               if pathlib.Path(f).exists()]
    for f in made:
        subprocess.run(["rm", "-f", f"/opt/orb/mem/{f}"], capture_output=True)
    if escaped:
        return False, "wrote outside the vault: " + ", ".join(escaped)
    return True, f"{len(attempts)} traversal attempts all contained in the vault"


def t_note_from_text():
    """A sentence becomes a note, and a question does not.

    The model extracts; the server writes. Extraction was measured at 15/15 on
    format, but it embellishes — asked for one item it produced three — so the
    body is checked for the invention that would otherwise land in the vault.
    """
    import random
    tag = f"suite trial {random.randint(10000, 99999)}"
    a = jpost("/note/from-text",
              {"text": f"make a note called {tag} with the first item being "
                       f"check the backup ran"}, timeout=300) or {}
    if not a.get("ok"):
        return False, f"did not write: {str(a)[:110]}"
    b = jpost("/note/from-text",
              {"text": f"add rotate the keys to my {tag} note"}, timeout=300) or {}
    body = ""
    f = pathlib.Path(f"/opt/orb/mem/{a['file']}")
    if f.exists():
        body = f.read_text(encoding="utf-8")
    subprocess.run(["rm", "-f", str(f)], capture_output=True)

    if b.get("action") != "appended":
        return False, f"append made a second note instead: {str(b)[:110]}"
    if "rotate the keys" not in body:
        return False, "the appended item is not in the file"
    if "NOTE|" in body:
        return False, "the extraction format leaked into the note body"
    # A question is not a note request, and answering one by filing it would be
    # a strange kind of wrong.
    c = jpost("/note/from-text", {"text": "what is the capital of France"},
              timeout=300) or {}
    if c.get("ok"):
        return False, "wrote a note for a plain question"
    return True, "created, appended to the same file, ignored a question"


def t_notes_search():
    """Short notes must be findable.

    load_vault() drops anything under FACT_MAX as a fact rather than a
    document, so "make me a note with one line on it" produces a file that
    retrieval cannot see. /notes reads the directory for exactly that reason —
    answering "no" about a file the user can see in Obsidian is the same
    failure as claiming one exists.
    """
    import random
    title = f"tiny note {random.randint(10000, 99999)}"
    a = jpost("/note", {"title": title, "body": "- one line"}, timeout=60) or {}
    hits = (jget(f"/notes?q={urllib.parse.quote(title)}", timeout=60) or {}).get("hits", [])
    subprocess.run(["rm", "-f", f"/opt/orb/mem/{a.get('file', 'x')}"],
                   capture_output=True)
    return bool(hits), (f"found {hits[0]['title']!r}" if hits
                        else "a short note was invisible to /notes")


def t_bridge_routes():
    """Each phrasing reaches the right capability.

    Ordering is what breaks: "is that in my notes?" contains the word notes and
    would otherwise be read as a request to write one.
    """
    cases = [("status", "status"), ("weather", "weather"),
             ("what the weather was like near me", "weather"),
             ("What is the weather", "weather"),
             ("what is the forecast", "weather"),
             ("what is weather", "chat"),
             ("is it going to rain", "weather"),
             ("how does weather forecasting work", "chat"),
             ("set location to Keswick", "setloc"),
             ("is that in the obsidian notes?", "check"),
             ("do i have a note about tls", "check"),
             ("make a note called shopping with milk on it", "make"),
             ("add rotate the keys to my server note", "make"),
             ("research the raspberry pi 5", "research"),
             ("look up wireguard", "research"),
             ("what is a semaphore", "chat"),
             ("how do i centre a div", "chat")]
    script = (
        "import sys, json; sys.path.insert(0, '/app'); import nova_bridge as B\n"
        "def route(t):\n"
        "    low = t.strip().lower()\n"
        "    if low in ('status','health',\"what's wrong\",'whats wrong'): return 'status'\n"
        "    if low in ('reset','forget','new chat'): return 'reset'\n"
        "    if low in ('help','commands','what can you do'): return 'help'\n"
        "    if B._SET_LOC.match(t): return 'setloc'\n"
        "    if B.wants_weather(t): return 'weather'\n"
        "    if B._NOTE_CHECK.search(t): return 'check'\n"
        "    if B._NOTE_MAKE.search(t): return 'make'\n"
        "    if B._RESEARCH.match(t): return 'research'\n"
        "    return 'chat'\n"
        f"print(json.dumps([route(t) for t, _ in {cases!r}]))")
    out = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return False, "could not reach the bridge"
    got = json.loads(out)
    bad = [f"{t!r}->{g}" for (t, want), g in zip(cases, got) if g != want]
    return not bad, "; ".join(bad) or f"{len(cases)} phrasings routed correctly"


def t_reminder_times():
    """Every phrasing lands on the hour it should, against a fixed clock.

    Time parsing is where the silent failures live: a reminder set for the
    wrong hour never announces itself, and the user finds out by missing the
    thing. Four of these were wrong on the first pass — "tomorrow at 8" became
    eight at night, and "timer for 10 minutes" found no time at all because the
    pattern only knew the word "in".

    Pinned against a fixed now, so this does not pass or fail by the hour it is
    run at.
    """
    cases = [("remind me in 20 minutes to take the bread out", "Sun 14:20", "take the bread out"),
             ("remind me in an hour to check the oven", "Sun 15:00", "check the oven"),
             ("remind me at 7pm to put the bins out", "Sun 19:00", "put the bins out"),
             ("remind me at 9am to book the mot", "Mon 09:00", "book the mot"),
             ("remind me at 7 to eat", "Sun 19:00", "eat"),
             ("remind me tomorrow at 8 to ring the vet", "Mon 08:00", "ring the vet"),
             ("remind me at 8 tomorrow to ring the vet", "Mon 08:00", "ring the vet"),
             ("timer for 10 minutes", "Sun 14:10", ""),
             ("set a timer for 90 seconds", "Sun 14:01", ""),
             ("remind me in 3 days to chase the invoice", "Wed 14:00", "chase the invoice")]
    script = (
        "import sys, time, json; sys.path.insert(0, '/app'); import nova_bridge as B\n"
        "NOW = time.mktime((2026, 8, 30, 14, 0, 0, 6, 242, -1))\n"
        "out = []\n"
        f"for text, _, _ in {cases!r}:\n"
        "    m = B._REMIND.match(text) or B._TIMER.match(text)\n"
        "    if not m:\n"
        "        out.append(['no match', '']); continue\n"
        "    when, rest = B.parse_when(m.group(1), now=NOW)\n"
        "    if when is None:\n"
        "        out.append(['no time', '']); continue\n"
        "    out.append([time.strftime('%a %H:%M', time.localtime(when)),\n"
        "                B.clean_task(rest)])\n"
        "print(json.dumps(out))")
    res = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60)
    if not res.stdout.strip():
        return False, f"could not run: {res.stderr.strip()[:110]}"
    got = json.loads(res.stdout)
    bad = [f"{t!r}->{g[0]} {g[1]!r}"
           for (t, wt, wk), g in zip(cases, got) if [wt, wk] != g]
    return not bad, "; ".join(bad)[:150] or f"{len(cases)} phrasings parsed correctly"


def t_reminder_fires():
    """Set one, watch it go off, confirm it is gone afterwards.

    The parser test proves the arithmetic; this proves the loop reads the file,
    sends, and removes. A reminder that fires forever is worse than one that
    never fires.
    """
    script = (
        "import sys, time, json; sys.path.insert(0, '/app'); import nova_bridge as B\n"
        "rid = B.add_reminder('__suite__', time.time() + 3, 'suite probe')\n"
        "print(rid)")
    rid = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not rid:
        return False, "could not add a reminder"
    time.sleep(25)
    left = subprocess.run(
        ["docker", "exec", "nova-bridge", "python3", "-c",
         "import sys, json; sys.path.insert(0, '/app'); import nova_bridge as B;"
         "print(json.dumps([r['id'] for r in B.load_state().get('reminders', [])]))"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    still = json.loads(left or "[]")
    return int(rid) not in still, (f"reminder {rid} fired and was cleared"
                                   if int(rid) not in still
                                   else f"reminder {rid} is still pending")


def t_closing_offer_stripped():
    """The EMPTY sign-off is deleted; a specific follow-up survives.

    The persona forbids the stock sign-offs by name and the model still reaches
    for one now and then — zero in eighteen replies, then straight back on the
    nineteenth — so the closed set is removed after the fact.

    The line this test draws moved when the persona was warmed up. It used to
    assert that "Let me know if you want the hourly" should go, on the grounds
    that it is an offer of help. It is, but it is a SPECIFIC one: it names the
    next thing and moves the conversation along, which is a friend being useful
    rather than a ticket being closed. Only the contentless offers go now, and
    the difference between the two is the whole point of the filter.
    """
    script = (
        "import sys, json; sys.path.insert(0, '/app'); import remote_proxy as R\n"
        "cases = ['I am fine. What can I help with today?',\n"
        "         'It is owner-only. How can I help you?',\n"
        "         'Done. Is there anything else you need?',\n"
        "         'Sorted. Let me know if you need anything else.',\n"
        "         'Rain later. Let me know if you want the hourly.',\n"
        "         'Done. Want me to add it to the upgrade note?',\n"
        "         'I do not know. Which version are you on?',\n"
        "         'That depends. Are you using systemd?']\n"
        "print(json.dumps([R.strip_closing_offer(c) for c in cases]))")
    out = subprocess.run(["docker", "exec", "orb-remote", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return False, "could not reach the router"
    got = json.loads(out)
    want = ["I am fine.", "It is owner-only.", "Done.", "Sorted.",
            # Kept from here down.
            "Rain later. Let me know if you want the hourly.",
            "Done. Want me to add it to the upgrade note?",
            "I do not know. Which version are you on?",
            "That depends. Are you using systemd?"]
    bad = [f"{g!r}" for g, w in zip(got, want) if g != w]
    return not bad, "; ".join(bad)[:130] or "4 empty sign-offs cut, 4 useful lines kept"


def t_knows_the_time():
    """Nova is told the hour, and names the right part of the day.

    It greeted with "Morning" at seven in the evening. Nothing had ever told it
    the time, and the persona's own example greeting began with the word
    "Morning" — an example is the strongest thing in a prompt, so that is what
    it copied, at every hour.

    Checks the part of day is correct for the router's clock rather than
    hard-coding one, so the test means the same thing whenever it is run.
    """
    script = (
        "import sys, json, datetime; sys.path.insert(0, '/app')\n"
        "import remote_proxy as R\n"
        "h = datetime.datetime.now().hour\n"
        "want = ('the early hours' if h < 5 else 'morning' if h < 12 else\n"
        "        'afternoon' if h < 18 else 'evening' if h < 22 else 'night')\n"
        "print(json.dumps([R.time_context(), want, h]))")
    out = subprocess.run(["docker", "exec", "orb-remote", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return False, "could not reach the router"
    line, want, hour = json.loads(out)
    if want not in line:
        return False, f"hour {hour} but the context says {line[:70]!r}"
    # And the clock itself has to be local. The container ran UTC for a day,
    # which would put this an hour out and be invisible in the wording.
    if datetime.datetime.now().strftime("%H") and str(hour) not in line:
        return False, f"hour {hour} not stated in {line[:70]!r}"
    return True, f"{want}, hour {hour}"


def t_opening_filler_stripped():
    """Praise for the question, and disclaiming a self, both cut from the front.

    Same technique as the closing sign-off and the same reason: the persona
    bans both by name, they arrive as paraphrases anyway, and a closed set of
    phrasings is deleted more reliably than it is instructed away.

    The greedy-quantifier case is pinned deliberately. "[^.!?]*" ran past the
    "but" to the end of the sentence and consumed the whole reply, sub()
    returned empty, and the never-return-nothing fallback handed back the
    original — so the filter looked inert when it was in fact firing far too
    well. The half after the "but" is the answer and has to survive.
    """
    q = chr(39)
    strip = [("I don" + q + "t think about personal preferences, but a bigger "
              "model would help.", "A bigger model would help."),
             ("I do not have personal preferences. SQLite is the better choice.",
              "SQLite is the better choice."),
             ("That" + q + "s a great question. Use SQLite.", "Use SQLite.")]
    keep = ["I think you should stay on the 3B.",
            "I don" + q + "t know.",
            "Nice one, that bridge was fiddly."]
    script = (
        "import sys, json; sys.path.insert(0, '/app'); import remote_proxy as R\n"
        f"print(json.dumps([R.strip_opening_praise(t) for t in "
        f"{[a for a, _ in strip] + keep!r}]))")
    out = subprocess.run(["docker", "exec", "orb-remote", "python3", "-c", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return False, "could not reach the router"
    got = json.loads(out)
    want = [b for _, b in strip] + keep
    bad = [f"{g!r}" for g, w in zip(got, want) if g != w]
    return not bad, "; ".join(bad)[:130] or "3 fillers cut, 3 real openings kept"


def t_notes_question_words():
    """"is X in my notes" must not search for a note called "notes".

    The whole question was passed to the matcher, which required every word in
    the title — so a note called "suite check", written seconds earlier, came
    back as not found because its title does not contain the word "notes".
    """
    import random
    title = f"framing check {random.randint(10000, 99999)}"
    a = jpost("/note", {"title": title, "body": "- x"}, timeout=60) or {}
    asked = f"is {title} in my obsidian notes"
    hits = (jget(f"/notes?q={urllib.parse.quote(asked)}", timeout=60) or {}).get("hits", [])
    subprocess.run(["rm", "-f", f"/opt/orb/mem/{a.get('file', 'x')}"],
                   capture_output=True)
    return bool(hits), ("found through the question framing" if hits
                        else "the framing words hid the note")


def t_rain_looks_ahead():
    """The forecast reports the hours to come, not the ones already gone.

    It said "100% chance of rain" on a bright morning, every morning. The
    figure was Open-Meteo's precipitation_probability_max, which is the maximum
    across the whole CALENDAR day and so includes the night that has already
    happened: it had rained at midnight, and every remaining hour of that day
    was between zero and four per cent.

    Honestly reported and consistently wrong, which is the worst kind — a
    forecast nobody believes is worse than no forecast at all.
    """
    day = "2026-08-31"
    fixtures = [
        # hours, "now", must say, must not say
        ([("00:00", 100), ("11:00", 2), ("14:00", 3), ("20:00", 0)],
         "11:00", "dry", "100"),
        ([("00:00", 100), ("11:00", 2), ("16:00", 75), ("20:00", 5)],
         "11:00", "16:00", "100"),
        # 45% is a risk, not a promise; calling it "likely" is how a forecast
        # stops being believed.
        ([("11:00", 5), ("15:00", 45)], "11:00", "possible", "likely"),
    ]
    bad = []
    for hours, at, want, unwanted in fixtures:
        payload = {"time": [f"{day}T{h}" for h, _ in hours],
                   "precipitation_probability": [p for _, p in hours]}
        script = (
            "import sys, json; sys.path.insert(0, '/app'); import nova_bridge as B\n"
            f"print(json.dumps(B.rain_ahead({payload!r}, now='{day}T{at}')))")
        out = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        if not out:
            return False, "could not reach the bridge"
        said = json.loads(out).lower()
        if want not in said or unwanted in said:
            bad.append(f"at {at}: {said!r}")
    return not bad, "; ".join(bad)[:150] or "3 fixtures report only the hours ahead"


def t_bridge_isolated():
    """The Telegram bridge's blast radius, asserted rather than assumed.

    It relays messages from the open internet, so it is the most exposed thing
    here and the first place an injection would land. It must not be able to
    read the vault (a personal note archive), and it must not see the model
    provider keys — mounting ./keys wholesale is the easy mistake, and it would
    hand a Telegram relay every API key on the box.
    """
    def inside(cmd):
        return subprocess.run(["docker", "exec", "nova-bridge", "sh", "-c", cmd],
                              capture_output=True, text=True, timeout=30)

    if inside("true").returncode != 0:
        return False, "nova-bridge is not running"
    bad = []
    if inside("ls /mem").returncode == 0:
        bad.append("can read the vault")
    keys = [k for k in inside("ls -A /run/keys").stdout.split()
            if k != "telegram.key"]
    if keys:
        bad.append("sees other keys: " + ", ".join(keys))
    return not bad, "; ".join(bad) or "no vault, no other keys"


def t_bridge_voice():
    """The whole voice path except the Telegram upload itself.

    Piper speaks a sentence, ffmpeg encodes the OGG/Opus that Telegram would
    carry, ffmpeg decodes it back to the 16 kHz mono WAV whisper wants, and
    whisper reads it. Four links, and a break in any one of them looks
    identical from the outside: the bot silently ignores voice notes.

    Asserted on word overlap rather than an exact string. base.en is allowed to
    punctuate differently; it is not allowed to lose the sentence.
    """
    said = "the backup ran nine hours ago and every service is responding"
    script = f'''
import json, pathlib, subprocess, tempfile, urllib.request
said = {said!r}
def http(url, data=None, headers=None):
    return urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers or {{}}), timeout=180)
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    wav = http("http://piper:5000/synthesize", json.dumps({{"text": said}}).encode(),
               {{"Content-Type": "application/json"}}).read()
    (d/"a.wav").write_bytes(wav)
    for args in (["-i", str(d/"a.wav"), "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", str(d/"b.ogg")],
                 ["-i", str(d/"b.ogg"), "-ar", "16000", "-ac", "1", "-f", "wav", str(d/"c.wav")]):
        r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error"] + args, capture_output=True)
        if r.returncode:
            raise SystemExit("ffmpeg: " + r.stderr.decode()[:200])
    b = "----novavoice"
    payload = (f"--{{b}}\\r\\n"
               'Content-Disposition: form-data; name="file"; filename="s.wav"\\r\\n'
               "Content-Type: audio/wav\\r\\n\\r\\n").encode() + (d/"c.wav").read_bytes() + \\
        (f"\\r\\n--{{b}}\\r\\n"
         'Content-Disposition: form-data; name="response_format"\\r\\n\\r\\njson\\r\\n'
         f"--{{b}}--\\r\\n").encode()
    out = http("http://whisper:8080/inference", payload,
               {{"Content-Type": f"multipart/form-data; boundary={{b}}"}})
    print(json.loads(out.read().decode()).get("text", "").strip())
'''
    r = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                       capture_output=True, text=True, timeout=300)
    heard = r.stdout.strip()
    if not heard:
        return False, f"no transcription: {r.stderr.strip()[:120]}"
    norm = lambda s: set("".join(c for c in s.lower() if c.isalnum() or c == " ").split())
    hit = len(norm(said) & norm(heard)) / max(1, len(norm(said)))
    return hit >= 0.8, f"{hit:.0%} of the sentence survived: {heard[:60]!r}"


def t_bridge_default_deny():
    """An unset allowlist must mean nobody, never everybody.

    A bot username is discoverable and anyone can message it. If an empty
    NOVA_TG_ALLOW were read as "no restriction", a stranger would get Nova with
    the whole vault attached, and nothing would look broken.
    """
    script = ("import os, importlib, sys; sys.path.insert(0, '/app');"
              "os.environ['NOVA_TG_ALLOW'] = '';"
              "import nova_bridge; importlib.reload(nova_bridge);"
              "print(len(nova_bridge.ALLOW))")
    out = subprocess.run(["docker", "exec", "nova-bridge", "python3", "-c", script],
                         capture_output=True, text=True, timeout=30).stdout.strip()
    if out != "0":
        return False, f"empty allowlist parsed as {out!r} entries"
    return True, "an empty allowlist authorises nobody"


# -------------------------------------------------------------- research ---
def t_research_floor():
    # Reports the code it actually got. The old message read "nonsense is
    # refused rather than written up" whether it passed or failed, which is
    # exactly as useful as saying nothing: an intermittent failure here gave no
    # clue whether the answer was a 200, a 500 or an empty string from a
    # timeout, and standalone runs would not reproduce it.
    code = code_of("/research", "POST",
                   {"q": "blorp glimf wuzzle", "agent": "fast"}, timeout=120)
    return code == "404", (f"nonsense refused with {code}" if code == "404"
                           else f"expected 404, got {code!r}")


def t_research_archive():
    evs, text = sse("/research", {"q": "what is a rainbow table", "agent": "fast"}, 300)
    note = next((e["orb_note"] for e in evs if "orb_note" in e), None)
    return bool(note and note.get("file")) and len(text) > 200, \
        f"{len(text)} chars, filed {(note or {}).get('file')}"


def t_research_web():
    """Research something the offline archive cannot know, from the live web.

    Distinguishes "our code is broken" from "the engines said no", because they
    are not the same finding and only one of them is actionable here.

    The free general engines rate-limit and CAPTCHA server-side traffic, and
    this suite is itself the load: every full run researches something live, so
    a handful of runs in a day exhausts them. That is a fact about public
    search engines, not a defect in Nova, and failing the build for it trains
    everyone to ignore a red suite.

    Returning None rather than False marks it not-applicable, so the reason is
    still printed and the count stays honest in both directions: this is not a
    pass either.
    """
    # Measures the condition that actually matters — the web returns nothing —
    # rather than naming the engines expected to be dead. An earlier version
    # required all four of brave, duckduckgo, google cse and startpage to be
    # listed unresponsive, so a run where one had recovered but still answered
    # nothing failed instead of being marked not-applicable.
    # Asked from INSIDE the docker network. This suite runs in the LXC, where
    # "searxng" does not resolve — the first version of this probe therefore
    # got nothing every time and skipped unconditionally, which is worse than
    # the failure it was meant to explain: a test that never runs reports
    # green forever.
    try:
        probe = json.loads(subprocess.run(
            ["docker", "exec", "orb-remote", "python3", "-c",
             "import urllib.request,sys;"
             "sys.stdout.write(urllib.request.urlopen("
             "'http://searxng:8080/search?q=nginx+reverse+proxy&format=json',"
             "timeout=40).read().decode())"],
            capture_output=True, text=True, timeout=60).stdout or "{}")
    except Exception:
        probe = {}
    if not probe.get("results"):
        dead = ", ".join(sorted(e[0] for e in probe.get("unresponsive_engines", [])))
        return None, f"the web returned nothing; engines refusing: {dead or 'unknown'}"

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
    """Piper makes audio, and whisper reads a FIXED recording exactly.

    This test used to synthesise a sentence and transcribe it, asserting an
    exact substring, on the stated reasoning that whisper is deterministic.
    Whisper is. PIPER IS NOT — measured: the same text three times gave three
    different files of 64044, 66092 and 68652 bytes, while the same audio gave
    whisper the identical transcript five times out of five.

    So the round trip was measuring Piper's noise scale and blaming whisper,
    and it failed the suite roughly one run in five with "grade reference",
    "greed reference" and "grid of reference". Worse, it was measuring the
    wrong thing entirely: in use a PERSON speaks, and Piper is nowhere in the
    input path.

    Now the two are separated. Piper only has to produce audio. Whisper is
    asked to read a recording committed alongside this file, so the assertion
    is exact and deterministic — which is the right bar, because this phrase
    feeds RE_WHERE, a regex command that a mis-hearing does not degrade but
    loses outright.
    """
    n = subprocess.run(["curl", "-s", "-m", "60", "-X", "POST", BASE + "/tts",
                        "-H", "Content-Type: application/json",
                        "-d", json.dumps({"text": "what is my grid reference"}),
                        "-o", "/dev/null", "-w", "%{size_download}"],
                       capture_output=True, text=True).stdout
    if int(n or 0) < 1000:
        return False, f"tts produced {n} bytes"

    ref = "/opt/orb/test-audio/grid-reference.wav"
    if not pathlib.Path(ref).exists():
        return False, f"reference recording missing at {ref}"
    out = subprocess.run(["curl", "-s", "-m", "120", "-X", "POST", BASE + "/stt",
                          "-F", f"file=@{ref}", "-F", "response_format=json"],
                         capture_output=True, text=True).stdout
    heard = json.loads(out).get("text", "").strip().lower()
    return "grid reference" in heard, f"tts {n} bytes; heard {heard!r}"


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
    ("nova", [("persona has not drifted", t_persona_no_drift, False),
              ("whole turn via /ask", t_ask, True),
              ("follows a thread", t_ask_history, True),
              ("bridge is isolated", t_bridge_isolated, False),
              ("bridge denies by default", t_bridge_default_deny, False),
              ("bridge voice round trip", t_bridge_voice, True),
              ("bridge routes commands", t_bridge_routes, False),
              ("note write and append", t_note_write, False),
              ("note titles are not paths", t_note_traversal, False),
              ("short notes are findable", t_notes_search, False),
              ("sentence becomes a note", t_note_from_text, True),
              ("reminder times parse", t_reminder_times, False),
              ("a reminder fires and clears", t_reminder_fires, True),
              ("closing offer stripped", t_closing_offer_stripped, False),
              ("note question framing", t_notes_question_words, False),
              ("opening filler stripped", t_opening_filler_stripped, False),
              ("knows the time of day", t_knows_the_time, False),
              ("rain forecast looks ahead", t_rain_looks_ahead, False)]),
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
            # The reason matters: "skipped" alone hides whether it was --quick
            # or an outside service refusing, and those need different actions.
            print(f"    SKIP  {name:34} {detail}")
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
