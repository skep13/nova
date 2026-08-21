"""Multi-agent router: one OpenAI-shaped endpoint, several free backends.

The page picks an agent by name; this decides where the request actually goes
and guarantees an answer either way.

    agent: "local"   -> llama.cpp in the next container. Always available.
    agent: <other>   -> a free hosted provider, if a key for it is installed.
    anything failing -> silently back to local, so the orb never goes mute.

Every provider here speaks the OpenAI chat-completions shape, which is the
whole reason this file is short. The Anthropic version it replaces needed a
translation layer in both directions; these need a base URL and a key, so all
four share a single code path and the streaming case is close to a byte relay.

Keys live one-per-file in /run/keys/<agent>.key, mounted read-only. No key
means the agent is simply never offered — there is no half-configured state,
and nothing here can spend money because none of these backends bill.

OFFLINE IS THE DEFAULT, NOT THE FALLBACK. Orb is a search-and-rescue device:
local answers everything unless the user deliberately picks otherwise, and any
remote failure lands straight back on local rather than surfacing an error.
"""
import bisect
import datetime
import json
import math
import os
import pathlib
import re
import time

import aiohttp
from aiohttp import web

LOCAL_URL = os.environ.get("LOCAL_URL", "http://llama:8080/v1/chat/completions")
KEY_DIR = pathlib.Path(os.environ.get("KEY_DIR", "/run/keys"))
LOG_DIR = pathlib.Path(os.environ.get("LOG_DIR", "/logs"))

# Only the tail of a conversation is worth resending. Free tiers are limited by
# tokens-per-minute far more often than by requests, so this protects the thing
# that actually runs out.
HISTORY_TURNS = int(os.environ.get("REMOTE_HISTORY_TURNS", "6"))
MAX_TOKENS = int(os.environ.get("REMOTE_MAX_TOKENS", "700"))
TIMEOUT_S = int(os.environ.get("REMOTE_TIMEOUT", "60"))

# Tags the page puts on messages that exist only to prop up a 1.5B. A hosted
# 70B needs none of them, and dropping them is ~650 tokens off every remote
# request — which on a 12K-tokens-per-minute free tier is the difference
# between a working assistant and a rate-limited one.
#   example   - few-shot turns teaching a tone      (~200 tok)
#   reference - Wikipedia excerpt from the archive  (~300 tok)
#   style     - remedial prompt coaching            (~150 tok)
# 'memory' and the user's own notes are NOT dropped: no hosted model can know
# them, so they are the one thing worth the tokens.
DROP_FOR_REMOTE = {"example", "reference", "style"}


# --- the roster -------------------------------------------------------------
# label   : what the user sees on the rail
# model   : overridable per agent, because hosted model IDs get retired often
#           and a rename should never need a rebuild
# note    : the free allowance, so /agents is self-documenting
AGENTS = [
    {
        "name": "local",
        "label": "local",
        "url": LOCAL_URL,
        "model": None,                       # llama serves whatever it loaded
        "note": "offline, always available",
    },
    {
        "name": "fast",
        "label": "fast",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "note": "Groq · ~1000 req/day, 12K tokens/min",
    },
    # Was Cerebras. Dropped 2026-08-16: their free credits require a card on
    # file and expire after 30 days, which is a metered account by another
    # name. OpenRouter needs no card and its :free models cost nothing at a
    # zero balance.
    {
        "name": "deep",
        "label": "deep",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-r1:free"),
        "note": "OpenRouter · ~50 req/day, 20/min",
    },
    {
        "name": "wide",
        "label": "wide",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"),
        "note": "NVIDIA · 1000 credits, 40 req/min",
    },
    {
        "name": "long",
        "label": "long",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": os.environ.get("GEMINI_MODEL", "gemini-3.7-flash"),
        "note": "Google AI Studio · ~1500 req/day, 1M context",
        # Gemini 3.x reasons before answering and that thinking is billed
        # against max_tokens while being invisible in the reply. Measured: 392
        # total tokens for a 44-token answer. At the shared 700 the thinking
        # eats half the budget and a long procedure truncates mid-step, which
        # looks exactly like the model giving up. Its own ceiling instead.
        "max_tokens": int(os.environ.get("GEMINI_MAX_TOKENS", "2000")),
    },
]
BY_NAME = {a["name"]: a for a in AGENTS}

# Last upstream error per agent. A wrong model ID is the single most likely
# failure here — provider catalogues churn — and without this it looks
# identical to "no key", which sends you debugging the wrong thing.
_last_error = {}

# Configuration failures, as opposed to transient ones. A bad key, a retired
# model or an unfunded account will fail identically on every request, and an
# agent in that state must stop being offered — otherwise the rail button
# silently serves local answers under a remote label, which is worse than the
# agent simply not being there.
#
# Rate limits (429) and server errors are deliberately NOT in here: those are
# temporary, and falling back for one request is the correct response.
HARD_CODES = ("401", "402", "403", "404")
HARD_COOLDOWN_S = 600           # re-offer after 10 min, so a fixed account heals
_hard_fail = {}                 # agent name -> (monotonic seconds, reason)


def read_key(name):
    try:
        return (KEY_DIR / f"{name}.key").read_text(encoding="utf-8").strip() or None
    except Exception:
        return None


def note_failure(name, err):
    _last_error[name] = err[:300]
    if err.split(":", 1)[0].strip() in HARD_CODES:
        _hard_fail[name] = (time.monotonic(), err[:300])


def note_success(name):
    _last_error.pop(name, None)
    _hard_fail.pop(name, None)


def hard_failed(name):
    hit = _hard_fail.get(name)
    if not hit:
        return None
    if time.monotonic() - hit[0] > HARD_COOLDOWN_S:
        _hard_fail.pop(name, None)          # cooldown over: let it try again
        return None
    return hit[1]


def available(agent):
    if agent["name"] == "local":
        return True
    return bool(read_key(agent["name"])) and not hard_failed(agent["name"])


# --- logging ----------------------------------------------------------------
# Deliberately /logs and NOT /mem: the page ingests every .md under mem and
# injects it into prompts, so logging there would poison the context within a
# day. These are a record, not a memory.
def slug(s, n=48):
    return (re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")[:n] or "exchange").rstrip("-")


# The local model's name is asked of llama rather than assumed. It used to be
# a hardcoded "qwen2.5-1.5b" fallback, which silently kept claiming 1.5B after
# the box was upgraded to a 3B — every local log line was wrong, and the logs
# are the only record of which brain answered.
_local_model = None


async def local_model_name(session):
    global _local_model
    if _local_model:
        return _local_model
    try:
        base = LOCAL_URL.rsplit("/chat/completions", 1)[0] + "/models"
        async with session.get(base, timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = (await r.json()).get("data") or []
            if data:
                _local_model = data[0].get("id")
    except Exception:
        pass
    return _local_model or "local (name unavailable)"


def log_exchange(question, answer, agent_name, model):
    if not (question and answer):
        return
    try:
        now = datetime.datetime.now()
        day = LOG_DIR / now.strftime("%Y-%m-%d")
        day.mkdir(parents=True, exist_ok=True)
        (day / f"{now.strftime('%H%M%S')}-{slug(question)}.md").write_text(
            "---\n"
            f"created: {now.isoformat(timespec='seconds')}\n"
            f"agent: {agent_name}\n"
            f"model: {model or 'unknown'}\n"
            "---\n\n"
            f"# {question.strip()[:200]}\n\n{answer.strip()}\n",
            encoding="utf-8")
        if agent_name not in ("local", "recall"):
            _recall[recall_key(question)] = (answer.strip(), agent_name, model)
    except Exception:
        pass                                # logging must never break a reply


# --- recall: the log corpus, read back --------------------------------------
# Logging was always meant to outlive the thing that produced it — the point of
# recording every exchange was that the good answers stay available once the
# network, or the paid key, is gone. The read path lived in the Anthropic proxy
# and was deleted along with it, so for a while this was a write-only archive.
#
# Only answers from REMOTE agents are recalled. Replaying a local answer saves
# nothing (the model is right there and will happily regenerate it) and risks
# serving something staler than what the model would say now. A Groq answer
# recorded at home, replayed on a hillside with no signal, is the whole idea.
_recall = {}

# Filler carries no meaning but stops "what is the capital of France" matching
# "whats the capital of france". Word ORDER is preserved deliberately: sorting
# the terms would collide "is a raven bigger than a crow" with its reverse, and
# a confidently wrong recalled answer is far worse than regenerating one.
_FILLER = re.compile(
    r"\b(?:the|a|an|is|are|was|were|do|does|did|of|to|for|in|on|at|it|its|"
    r"please|can|could|you|your|me|my|i|whats|what|tell|about)\b")


def recall_key(q):
    q = re.sub(r"[^a-z0-9 ]+", " ", (q or "").lower())
    return " ".join(_FILLER.sub(" ", q).split())


def load_recall():
    """Rebuild the cache from disk at startup, so it survives a restart."""
    if not LOG_DIR.exists():
        return
    for p in sorted(LOG_DIR.rglob("*.md")):          # oldest first: newest wins
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
            head, _, body = txt.partition("\n---\n\n")
            agent = re.search(r"^agent: (.+)$", head, re.M)
            model = re.search(r"^model: (.+)$", head, re.M)
            if not agent or agent.group(1).strip() in ("local", "recall"):
                continue
            q = re.search(r"^# (.+)$", body, re.M)
            if not q:
                continue
            answer = body.split(q.group(0), 1)[-1].strip()
            if answer:
                _recall[recall_key(q.group(1))] = (
                    answer, agent.group(1).strip(),
                    model.group(1).strip() if model else "")
        except Exception:
            pass


# --- request shaping --------------------------------------------------------
def remote_payload(agent, payload):
    """Rebuild the request for a hosted provider, allowlist style.

    Deliberately NOT a copy-and-tweak of the incoming body. It carries
    llama.cpp-only fields (repeat_penalty) and per-message `name` tags that
    strict providers reject outright, and a 400 from a free tier is
    indistinguishable from being out of quota. Only known-good keys go out.
    """
    msgs = [m for m in payload.get("messages", [])
            if m.get("name") not in DROP_FOR_REMOTE]

    system = [m.get("content", "") for m in msgs if m.get("role") == "system"]
    turns = [{"role": m["role"], "content": m.get("content", "")}
             for m in msgs if m.get("role") in ("user", "assistant") and m.get("content")]

    if len(turns) > HISTORY_TURNS:
        turns = turns[-HISTORY_TURNS:]
    while turns and turns[0]["role"] != "user":
        turns.pop(0)                        # every provider wants a user turn first

    out = []
    if system:
        out.append({"role": "system", "content": "\n\n".join(s for s in system if s)})
    out.extend(turns)

    # The remote budget WINS over the page's request — it is not a ceiling.
    #
    # The page asks for 600 because that is what llama.cpp needs to finish a
    # procedure at 13 tok/s: a number about local generation speed, not about
    # the model. Applied to a hosted model it truncates mid-step, which reads
    # as the model giving up. Measured: deepseek-v4-flash cut off at "6. Apply
    # an antiseptic (optional" on exactly this question.
    #
    # Output on these tiers is free and fast, so there is nothing to protect by
    # capping it low. Per-agent overrides exist for reasoning models, which
    # spend most of their allowance on thinking the user never sees.
    limit = agent.get("max_tokens") or MAX_TOKENS

    body = {
        "model": agent["model"],
        "messages": out,
        "stream": bool(payload.get("stream")),
        "max_tokens": limit,
    }
    if payload.get("temperature") is not None:
        body["temperature"] = max(0.0, min(1.0, float(payload["temperature"])))
    return body


def text_from(chunk):
    """Pull assistant text out of one OpenAI SSE delta, for the log."""
    try:
        return chunk["choices"][0].get("delta", {}).get("content", "") or ""
    except Exception:
        return ""


async def relay(url, body, headers, request, resp, collected, timeout_s):
    """Stream an OpenAI-shaped upstream through untouched.

    Both ends speak the same wire format, so bytes pass straight through and
    only a copy is tapped off for the log — no re-encoding, no buffering.

    The ordering matters: the response is prepared only AFTER the upstream has
    answered 200. Raising before that point means nothing has reached the
    browser yet, which is what lets the caller fall back to local invisibly
    rather than leaving a half-written bubble that restarts itself.
    """
    # sock_read, NOT total. A total timeout kills a stream for being long,
    # which is exactly what a good answer to "give me the steps" looks like —
    # measured 30-40s for a full first-aid procedure. What actually indicates
    # trouble is a stream that STOPS producing, so bound the gap between
    # chunks instead of the whole response. Connect is bounded separately so a
    # black-holed provider still fails fast.
    timeout = aiohttp.ClientTimeout(sock_connect=15, sock_read=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(url, json=body, headers=headers or {}) as r:
            if r.status != 200:
                raise RuntimeError(f"{r.status}: {(await r.text())[:300]}")
            if resp is not None and not resp.prepared:
                await resp.prepare(request)
            async for raw in r.content:
                if resp is not None:
                    await resp.write(raw)
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("data:"):
                    b = line[5:].strip()
                    if b and b != "[DONE]":
                        try:
                            collected.append(text_from(json.loads(b)))
                        except Exception:
                            pass


async def chat(request):
    payload = await request.json()
    # Popped, not read: the remainder is forwarded verbatim on the local path
    # and llama has no business seeing a field meant for this router.
    want = payload.pop("agent", "local") or "local"
    stream = bool(payload.get("stream"))
    question = next((m.get("content", "") for m in reversed(payload.get("messages", []))
                     if m.get("role") == "user"), "")

    agent = BY_NAME.get(want, BY_NAME["local"])
    if not available(agent):
        agent = BY_NAME["local"]            # key pulled since the page loaded

    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream",
                                       "Cache-Control": "no-cache",
                                       "X-Accel-Buffering": "no"})
    collected = []

    # Recall runs only on the LOCAL path — i.e. offline, or by choice. If a
    # remote agent is selected and reachable, it answers fresh; replaying an
    # old answer over a working network would be a downgrade, not a saving.
    if agent["name"] == "local" and question:
        hit = _recall.get(recall_key(question))
        if hit:
            answer, src_agent, src_model = hit
            # Logged under its own agent name so the record stays honest about
            # where the words came from and that they were not regenerated.
            log_exchange(question, answer, "recall", f"{src_agent}/{src_model}")
            if stream:
                await resp.prepare(request)
                await resp.write(("data: " + json.dumps(
                    {"choices": [{"index": 0, "delta": {"content": answer}}]}) + "\n\n").encode())
                await resp.write(b"data: [DONE]\n\n")
                return resp
            return web.json_response({
                "model": f"recall:{src_model}",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": answer}}]})

    if agent["name"] != "local":
        key = read_key(agent["name"])
        body = remote_payload(agent, payload)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            if stream:
                await relay(agent["url"], body, headers, request, resp,
                            collected, TIMEOUT_S)
            else:
                timeout = aiohttp.ClientTimeout(total=TIMEOUT_S)
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.post(agent["url"], json=body, headers=headers) as r:
                        if r.status != 200:
                            raise RuntimeError(f"{r.status}: {(await r.text())[:300]}")
                        out = await r.json()
                collected = [out["choices"][0]["message"]["content"]]
                note_success(agent["name"])
                log_exchange(question, collected[0], agent["name"], agent["model"])
                return web.json_response(out)

            note_success(agent["name"])
            log_exchange(question, "".join(collected), agent["name"], agent["model"])
            return resp
        except Exception as exc:
            # Rate limit, wrong model ID, expired key, no network — all the
            # same from here: remember why, then answer anyway.
            note_failure(agent["name"], str(exc))
            if resp.prepared:
                await resp.write(b"data: [DONE]\n\n")
                return resp
            collected = []

    # Local: the default, and the safety net under every branch above.
    if stream:
        await relay(LOCAL_URL, payload, None, request, resp, collected, 900)
        await resp.write(b"data: [DONE]\n\n")
        log_exchange(question, "".join(collected), "local", None)
        return resp

    timeout = aiohttp.ClientTimeout(total=900)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(LOCAL_URL, json=payload) as r:
            out = await r.json()
    try:
        # llama echoes the model it loaded on every response - authoritative,
        # and free compared with a separate lookup.
        log_exchange(question, out["choices"][0]["message"]["content"], "local",
                     out.get("model"))
    except Exception:
        pass
    return web.json_response(out)


# --- offline place lookup ---------------------------------------------------
# "Where am I" answered as a grid reference is right for a radio and useless for
# everything else. This turns a fix into something a person can picture, with no
# network: GeoNames GB, populated places plus the named high ground people
# actually navigate by, 62k entries in 2.5 MB.
#
# Deliberately not a street-address geocoder. Reverse geocoding to a house
# number needs either a network round trip to someone else's server (exactly
# what a search-and-rescue device cannot rely on) or a full OSM extract and a
# PostGIS instance, which this box has neither the disk nor the RAM for. A
# named place with a distance and a bearing is more useful in the field anyway:
# "600 m north-east of Seathwaite" can be walked to; a postcode cannot.
PLACES_FILE = pathlib.Path(os.environ.get("PLACES_FILE", "/data/places.json"))
_places = []          # [name, lat, lon, population, feature] sorted by lat
_lats = []            # just the latitudes, so bisect has something to compare


def load_places():
    global _places, _lats
    try:
        _places = json.loads(PLACES_FILE.read_text(encoding="utf-8"))
        # A parallel array of latitudes is not redundancy — bisect on the rows
        # themselves compares whole lists starting at the NAME, so it returned
        # index 0 every time and quietly scanned all 62k entries per lookup.
        _lats = [row[1] for row in _places]
    except Exception:
        _places, _lats = [], []


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def nearest_places(lat, lon, min_pop=0, span_deg=0.35):
    """Nearest entry to a point, searched within a latitude band.

    The list is sorted by latitude, so bisect narrows 62k candidates to a few
    hundred before any trigonometry runs. Without that this is 62k haversines
    per fix, twice, on a CPU already shared with the model.
    """
    if not _places:
        return None
    lo = bisect.bisect_left(_lats, lat - span_deg)
    hi = bisect.bisect_right(_lats, lat + span_deg)
    best, best_d = None, None
    for row in _places[lo:hi]:
        if row[3] < min_pop:
            continue
        d = _haversine(lat, lon, row[1], row[2])
        if best_d is None or d < best_d:
            best, best_d = row, d
    if best is None:
        return None
    return {"name": best[0], "population": best[3], "feature": best[4],
            "distance_m": round(best_d), "bearing": round(_bearing(lat, lon, best[1], best[2]))}


async def place(request):
    """lat/lon -> the nearest named place, and the nearest sizeable town."""
    try:
        lat = float(request.query["lat"])
        lon = float(request.query["lon"])
    except Exception:
        return web.json_response({"error": "lat and lon required"}, status=400)
    near = nearest_places(lat, lon)
    # A second, wider search for somewhere recognisable. The nearest hamlet may
    # mean nothing to the person on the other end of the radio; the nearest town
    # usually does.
    town = nearest_places(lat, lon, min_pop=2000, span_deg=0.9)
    if town and near and town["name"] == near["name"]:
        town = None
    return web.json_response({"nearest": near, "town": town,
                              "places_loaded": len(_places)})


async def diag(request):
    """One-line-per-event diagnostic sink for the page.

    Speech recognition fails on the DEVICE, in Safari, in ways no amount of
    reading the source reproduces — and the status line that reports it clears
    after a second, so it is routinely missed. This lets the phone say what
    happened somewhere it can be read later.

    Deliberately dumb: append a line, never fail the caller. No transcript text
    is accepted or stored — only lifecycle timings and capability flags.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    keep = {k: body.get(k) for k in
            ("event", "error", "ms", "standalone", "secure", "display", "ua", "mode")}
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "diag.log").open("a", encoding="utf-8") as f:
            stamp = datetime.datetime.now().isoformat(timespec="seconds")
            f.write(stamp + " " + json.dumps(keep, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return web.json_response({"ok": True})


async def agents(request):
    """What the page builds its picker from. Unavailable agents are listed but
    flagged, so a missing key is visible rather than a silently absent button."""
    async with aiohttp.ClientSession() as sess:
        local_name = await local_model_name(sess)
    return web.json_response({
        "agents": [{
            "name": a["name"],
            "label": a["label"],
            # Local reports whatever llama actually loaded, so the picker can
            # never disagree with reality about which brain is answering.
            "model": a["model"] or local_name,
            "note": a["note"],
            "available": available(a),
            "last_error": _last_error.get(a["name"]),
            "disabled_reason": hard_failed(a["name"]),
        } for a in AGENTS],
        "history_turns": HISTORY_TURNS,
        "max_tokens": MAX_TOKENS,
        "recalled_answers": len(_recall),
    })


app = web.Application(client_max_size=8 * 1024 * 1024)
app.add_routes([
    web.post("/v1/chat/completions", chat),
    web.get("/agents", agents),
    web.post("/diag", diag),
    web.get("/place", place),
])

if __name__ == "__main__":
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    load_recall()          # previous remote answers are free to serve offline
    load_places()          # offline place names for turning a fix into words
    web.run_app(app, host="0.0.0.0", port=5003, print=None)
