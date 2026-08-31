"""Nova over Telegram: a way to talk to her, and a way for her to speak first.

Two things the web page cannot do. It cannot be reached when it is not open,
and it cannot get your attention — the backup died on 22 August and stayed dead
for seven days precisely because nothing was able to tell anyone. A bot message
is a push notification on a phone, so one mechanism covers both directions.

WHY TELEGRAM, and not the WhatsApp that was asked for.

Telegram supports long polling: this process dials OUT and holds the connection
open. Nothing listens on a port, nothing is published, and Tailscale Funnel
stays off — which matters here more than usual, because the WebDAV vault is
served without authentication by request, and a public endpoint on this box
would expose it. WhatsApp's official Cloud API requires an inbound HTTPS
webhook, so it cannot be done without that exposure; the unofficial libraries
avoid the webhook but attach to a personal number in violation of the terms,
and the number that gets banned is the user's own.

WHAT THIS IS NOT. iOS does not let any application read another application's
notifications — there is no equivalent of Android's notification listener, and
no entitlement that grants it. Nova cannot announce an incoming WhatsApp or
email that arrives on the phone. She can only tell you things she worked out
herself, which is what the alerting half of this file is for.

SECURITY. A bot's username is discoverable and anyone may message it, so the
allowlist is default-deny. Without it, a stranger gets an assistant with the
whole vault attached — a personal note archive, not a public encyclopedia.

Enrolment is by one-time code rather than by trusting whoever messages first.
Trust-on-first-use would be simpler and is wrong here: between the token being
installed and the owner sending a message there is a window in which anyone who
knows the bot's name is the first, and the failure is silent and permanent. The
code is generated away from this machine, carried in the environment, and
retired the moment it is used.
"""
import asyncio
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import aiohttp

ASK_URL = os.environ.get("NOVA_ASK_URL", "http://remote:5003/ask")
HEALTH_URL = os.environ.get("NOVA_HEALTH_URL", "http://remote:5003/health")
STT_URL = os.environ.get("NOVA_STT_URL", "http://whisper:8080/inference")
TTS_URL = os.environ.get("NOVA_TTS_URL", "http://piper:5000/synthesize")
# The vault is reached through the router, never mounted here. This process
# relays messages from the open internet; giving it the filesystem as well
# would put the note archive one bug away from the outside.
NOTES_URL = os.environ.get("NOVA_NOTES_URL", "http://remote:5003/notes")
NOTE_FROM_TEXT_URL = os.environ.get("NOVA_NOTE_URL",
                                    "http://remote:5003/note/from-text")
RESEARCH_URL = os.environ.get("NOVA_RESEARCH_URL", "http://remote:5003/research")

HELP = (
    "Ask me anything and I'll answer from your vault or what I know.\n\n"
    "status - how I am, checked rather than guessed\n"
    "weather - current conditions where you are\n"
    "set location <postcode or town> - for weather and the morning brief\n"
    "research <topic> - the vault, the offline encyclopedia, then the web\n"
    "make a note called X saying Y - writes it into Obsidian\n"
    "add Y to my X note - appends to one that exists\n"
    "is X in my notes - checked against the actual files\n"
    "remind me in 20 minutes to X / remind me at 7pm to X\n"
    "timer for 10 minutes\n"
    "reminders - what is set; cancel 3; cancel all\n"
    "reset - forget this conversation\n\n"
    "Voice notes work. Send one and you get one back."
)
KEY_FILE = pathlib.Path(os.environ.get("TG_KEY", "/run/keys/telegram.key"))
STATE_FILE = pathlib.Path(os.environ.get("BRIDGE_STATE", "/logs/bridge-state.json"))

# Numeric chat IDs, comma separated. Empty means nobody, deliberately: an
# accidentally empty variable must lock the bot down rather than open it up.
ALLOW = {c.strip() for c in os.environ.get("NOVA_TG_ALLOW", "").split(",") if c.strip()}

# The one-time enrolment code. Sent as the first message by whoever should own
# this bot; anyone else is refused without being told why, because telling a
# stranger that a code exists is telling them what to look for.
ENROL_CODE = os.environ.get("NOVA_TG_ENROL", "").strip()

HEALTH_EVERY = int(os.environ.get("NOVA_HEALTH_EVERY", "300"))
MAX_REPLY = 3800          # Telegram's limit is 4096; leave room for a prefix
PER_MIN = int(os.environ.get("NOVA_TG_PER_MIN", "12"))
MAX_VOICE_S = int(os.environ.get("NOVA_MAX_VOICE_S", "120"))
# Piper is not fast on two cores and a long reply read aloud is not wanted on a
# phone anyway. Past this, the text stands on its own.
MAX_SPEAK_CHARS = int(os.environ.get("NOVA_MAX_SPEAK_CHARS", "700"))

_seen = {}                # chat id -> [timestamps], for the rate limit
_history = {}             # chat id -> [(role, content), ...]
HISTORY_TURNS = 6

HAVE_FFMPEG = bool(shutil.which("ffmpeg"))


def log(msg):
    """Say what happened, on stdout, where docker logs will keep it.

    This file logged NOTHING for its first day, and the first real failure was
    consequently undiagnosable from the outside: the bot read messages and said
    nothing, and there was no way to tell whether an update had even arrived.
    Silence is a fine reply to a stranger; it is a terrible operational record.

    Never logs message text or the token. Chat ids and outcomes only — enough
    to see the shape of what happened without keeping a copy of the
    conversation on disk.
    """
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}", flush=True)


def _norm_code(s):
    """Codes compared on their words, ignoring case and punctuation."""
    return "".join(c for c in (s or "").lower() if c.isalnum())


def token():
    """The bot token, read at use rather than held in a module global.

    Same handling as the model keys: mounted read-only, never logged, never
    included in an error message. A token in a traceback is a token in a log
    file, and this one grants the ability to impersonate Nova.
    """
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def allowed():
    """Everyone permitted: configured in the environment, plus anyone enrolled.

    Read from disk each time rather than cached, so enrolling takes effect
    immediately and survives a restart without the compose file being edited.
    """
    return ALLOW | set(load_state().get("enrolled", []))


def rate_ok(chat):
    """A crude per-chat ceiling.

    Not protection against an attacker — the allowlist is that — but against a
    loop. A retry storm or a mis-wired automation talking to a two-core laptop
    would otherwise queue model calls until nothing else could run.
    """
    now = time.time()
    hits = [t for t in _seen.get(chat, []) if now - t < 60]
    hits.append(now)
    _seen[chat] = hits
    return len(hits) <= PER_MIN


def remember(chat, role, content):
    h = _history.setdefault(chat, [])
    h.append((role, content))
    del h[:-HISTORY_TURNS * 2]


def try_enrol(chat, text):
    """Claim the bot with the one-time code. Returns a reply, or None.

    Single use: the code is burned on success, so a code that leaks after the
    fact is worth nothing. On failure this says nothing about codes at all —
    an unknown sender learns only that they are not authorised.
    """
    state = load_state()
    if not ENROL_CODE or state.get("enrol_used"):
        return None
    # Normalised, not compared raw. A phone keyboard autocapitalises the first
    # letter of a message, so "Nova-cedar-..." never matched "nova-cedar-..."
    # and the only symptom was silence — the bot appearing to read messages and
    # ignore them. Case and stray punctuation carry no entropy here; the words
    # do. Being strict about them bought nothing and cost the whole feature.
    if _norm_code(text) != _norm_code(ENROL_CODE):
        log(f"enrolment refused for chat {chat}: code did not match")
        return None
    enrolled = set(state.get("enrolled", []))
    enrolled.add(chat)
    state["enrolled"] = sorted(enrolled)
    state["enrol_used"] = True
    save_state(state)
    return ("Enrolled — this chat is now the only one I answer, and that code "
            "is spent. Say 'status' for how I am, or just ask me something. "
            "Send a voice note and I will reply with one.")


async def send(session, chat, text):
    """One message out. Long replies are split rather than truncated."""
    tok = token()
    if not tok:
        return
    text = (text or "").strip() or "(no answer)"
    while text:
        chunk, text = text[:MAX_REPLY], text[MAX_REPLY:]
        try:
            async with session.post(
                    f"https://api.telegram.org/bot{tok}/sendMessage",
                    json={"chat_id": chat, "text": chunk,
                          "disable_web_page_preview": True}) as r:
                await r.read()
        except Exception:
            return          # a failed send is not worth killing the loop over


# --- voice ------------------------------------------------------------------
#
# Telegram sends voice notes as OGG/Opus; whisper.cpp wants 16 kHz mono WAV;
# Telegram's sendVoice wants OGG/Opus back. So ffmpeg sits on both ends. It is
# the only reason this image is not python:slim and nothing else, and it is
# worth it: this is a voice assistant, and reaching it by typing on a phone is
# the least useful version of it.
#
# If ffmpeg is missing the bridge degrades to text rather than failing — a
# spoken message gets a written answer, which is worse but not broken.

def _run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, timeout=timeout).returncode == 0


async def voice_to_text(session, file_id):
    """Download a voice note and transcribe it. Returns text, or None."""
    tok = token()
    if not (tok and HAVE_FFMPEG):
        return None
    try:
        async with session.get(f"https://api.telegram.org/bot{tok}/getFile",
                               params={"file_id": file_id}) as r:
            path = (await r.json())["result"]["file_path"]
        async with session.get(
                f"https://api.telegram.org/file/bot{tok}/{path}") as r:
            blob = await r.read()
    except Exception:
        return None

    with tempfile.TemporaryDirectory() as d:
        src, wav = pathlib.Path(d) / "in.oga", pathlib.Path(d) / "out.wav"
        src.write_bytes(blob)
        # 16 kHz mono is what the model was trained on; anything else is
        # resampled internally at best and mis-decoded at worst.
        if not _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(src),
                     "-ar", "16000", "-ac", "1", "-f", "wav", str(wav)]):
            return None
        try:
            form = aiohttp.FormData()
            form.add_field("file", wav.read_bytes(), filename="speech.wav",
                           content_type="audio/wav")
            form.add_field("response_format", "json")
            async with session.post(STT_URL, data=form) as r:
                out = await r.json(content_type=None)
        except Exception:
            return None
    return (out.get("text") or "").strip() or None


async def send_voice(session, chat, text):
    """Speak a reply. Best effort — the text has already been sent."""
    tok = token()
    if not (tok and HAVE_FFMPEG) or len(text) > MAX_SPEAK_CHARS:
        return
    try:
        async with session.post(TTS_URL, json={"text": text}) as r:
            wav_bytes = await r.read()
    except Exception:
        return
    if not wav_bytes:
        return

    with tempfile.TemporaryDirectory() as d:
        wav, ogg = pathlib.Path(d) / "in.wav", pathlib.Path(d) / "out.ogg"
        wav.write_bytes(wav_bytes)
        # sendVoice accepts OGG/Opus only. Anything else arrives as a file
        # attachment instead of a playable note, which is a poor substitute.
        if not _run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(wav),
                     "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", str(ogg)]):
            return
        try:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(chat))
            form.add_field("voice", ogg.read_bytes(), filename="nova.ogg",
                           content_type="audio/ogg")
            async with session.post(
                    f"https://api.telegram.org/bot{tok}/sendVoice", data=form) as r:
                await r.read()
        except Exception:
            return


# --- reminders and timers ----------------------------------------------------
#
# Parsed, not modelled. "in twenty minutes" and "at half seven" are a small
# regular grammar, and the failure modes of getting them wrong are the worst
# kind: a reminder that silently never fires is indistinguishable from one that
# was never set, and the user finds out by missing the thing.
#
# So the clock is arithmetic and the only thing the model would have been asked
# for — what the reminder is ABOUT — is just the rest of the sentence.
_UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
          "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
          "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
          "d": 86400, "day": 86400, "days": 86400,
          "w": 604800, "week": 604800, "weeks": 604800}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "fortyfive": 45, "sixty": 60, "half": 0.5,
}

# "in" and "for" both: a reminder is set "in 20 minutes" and a timer is set
# "for 10 minutes", and both are the same arithmetic.
_IN = re.compile(
    r"\b(?:in|for)\s+(\d+|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) +
    r")\s*(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b", re.I)

_AT = re.compile(r"\bat\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", re.I)

# Matched separately and removed before the time is parsed, rather than being
# an optional group on either side of it. As part of _AT it had to be written
# twice, the trailing copy never fired because the preceding \s* had already
# eaten its space, and "at 8 tomorrow" became eight tonight with the word
# "tomorrow" left sitting in the reminder text.
_TOMORROW = re.compile(r"\btomorrow\b", re.I)

_REMIND = re.compile(
    r"^\s*(?:can you\s+|please\s+)*(?:remind me|set a reminder|reminder)\b(.*)$", re.I)
_TIMER = re.compile(
    r"^\s*(?:can you\s+|please\s+)*(?:set (?:a|an)\s+|start (?:a|an)\s+)?timer\b(.*)$",
    re.I)
_LIST_REM = re.compile(r"^\s*(?:reminders|timers|list reminders|what.s set)\s*[?.]?\s*$", re.I)
_CANCEL = re.compile(r"^\s*cancel\s+(?:reminder\s+)?(\d+|all)\s*$", re.I)


def parse_when(text, now=None):
    """(epoch, remaining_text) for a time phrase, or (None, text).

    Handles "in 20 minutes" and "at 7pm", with "tomorrow" on either side of the
    time. An "at" time that has already passed today rolls to tomorrow, because
    someone saying "remind me at 7" at nine in the evening does not mean two
    minutes ago and does not mean never.
    """
    now = now or time.time()

    tomorrow = bool(_TOMORROW.search(text))
    if tomorrow:
        text = _TOMORROW.sub(" ", text)

    m = _IN.search(text)
    if m:
        raw, unit = m.group(1).lower(), m.group(2).lower()
        n = float(raw) if raw.isdigit() else _WORD_NUMBERS.get(raw, 0)
        if n <= 0:
            return None, text
        return now + n * _UNITS[unit], (text[:m.start()] + " " + text[m.end():]).strip()

    m = _AT.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if hour > 23 or minute > 59:
            return None, text
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        # No am/pm and an hour that has already gone today is read as the
        # evening: "remind me at 7" said at lunchtime means seven tonight, not
        # tomorrow morning.
        #
        # Not when tomorrow was said, though. "tomorrow at 8" means eight in
        # the morning, and shifting it by today's clock turned it into eight at
        # night — the reminder arrives, twelve hours late, which is the failure
        # that looks least like a failure.
        lt = time.localtime(now)
        assume_pm = (not ampm and not tomorrow and hour < 12
                     and (lt.tm_hour, lt.tm_min) > (hour, minute)
                     and hour + 12 > lt.tm_hour)
        if assume_pm:
            hour += 12
        target = list(lt)
        target[3], target[4], target[5] = hour, minute, 0
        when = time.mktime(time.struct_time(tuple(target)))
        if tomorrow or when <= now:
            when += 86400
        return when, (text[:m.start()] + " " + text[m.end():]).strip()

    return None, text


def clean_task(text):
    """The reminder itself, with the connecting words taken off the front."""
    t = re.sub(r"^\s*(?:to|that|about|it.s|its)\b\s*", "", text.strip(), flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.;:")
    return t


def add_reminder(chat, when, what):
    state = load_state()
    rems = state.get("reminders", [])
    rid = max([r.get("id", 0) for r in rems], default=0) + 1
    rems.append({"id": rid, "chat": str(chat), "at": when, "what": what})
    state["reminders"] = rems
    save_state(state)
    return rid


def when_words(when):
    """"in 20 minutes" reads better than a timestamp for anything soon."""
    delta = when - time.time()
    if delta < 3600:
        return f"in {max(1, round(delta / 60))} minutes"
    stamp = time.strftime("%H:%M", time.localtime(when))
    if time.strftime("%Y-%m-%d", time.localtime(when)) == time.strftime("%Y-%m-%d"):
        return f"at {stamp}"
    return f"at {stamp} on {time.strftime('%a %d %b', time.localtime(when))}"


async def watch_reminders(session):
    """Fire anything due, then forget it.

    Persisted to disk rather than held in memory, so a restart does not quietly
    drop everything anyone set. Checked every fifteen seconds: a reminder that
    arrives a quarter-minute late is fine, one that arrives after a redeploy is
    not.
    """
    while True:
        try:
            state = load_state()
            rems = state.get("reminders", [])
            now = time.time()
            due = [r for r in rems if r.get("at", 0) <= now]
            if due:
                for r in due:
                    await send(session, r["chat"], f"Reminder: {r['what']}")
                    log(f"reminder {r['id']} fired for chat {r['chat']}")
                # Re-read before writing: watch_health and watch_brief also
                # write this file, and clobbering their keys would re-announce
                # the health state or re-send the morning brief.
                state = load_state()
                keep = [r for r in state.get("reminders", [])
                        if r.get("id") not in {d["id"] for d in due}]
                state["reminders"] = keep
                save_state(state)
        except Exception as exc:
            log(f"reminder sweep failed: {type(exc).__name__}: {exc}")
        await asyncio.sleep(15)


# --- weather, and the morning brief -----------------------------------------
#
# Asked for "a brief every morning at 730 on local weather and temperature",
# Nova said to go and use a weather app. It was the first thing written into
# the upgrade list. This is it.
#
# Open-Meteo for both geocoding and forecast: free, no API key, no account, and
# no request signing — which is the entire reason, because the standing rule
# here is that nothing costs money and nothing needs a key that could expire
# and take a feature down silently.
#
# The location is not hardcoded. The only coordinates on this box are test
# fixtures — Tower Bridge, Scafell Pike — so the user sets theirs once with
# "set location <place>" and it persists.
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
BRIEF_AT = os.environ.get("NOVA_BRIEF_AT", "07:30")
# ISO-3166 alpha-2, searched before the rest of the world. Empty for no
# preference. This is a personal assistant with one user, and "Boston"
# meaning Lincolnshire rather than Massachusetts is the whole point.
HOME_COUNTRY = os.environ.get("NOVA_COUNTRY", "GB").strip().upper()

# WMO weather codes. Only the groups that read differently to a person; the
# exact code is no use in a sentence.
_WMO = [
    (0, 0, "clear"), (1, 1, "mostly clear"), (2, 2, "partly cloudy"),
    (3, 3, "overcast"), (45, 48, "foggy"), (51, 57, "drizzle"),
    (61, 65, "rain"), (66, 67, "freezing rain"), (71, 77, "snow"),
    (80, 82, "rain showers"), (85, 86, "snow showers"),
    (95, 99, "thunderstorms"),
]


def describe(code):
    for lo, hi, word in _WMO:
        if lo <= code <= hi:
            return word
    return "unsettled"


# A UK postcode is how a British person says where they live, and Open-Meteo's
# geocoder indexes settlements — it returns nothing at all for "SW1A 1AA". So
# postcodes go to postcodes.io instead: free, no key, no account, and the
# authoritative source rather than a guess.
#
# Both halves optional-spaced, and the outcode alone accepted, because "SW1A" is
# a perfectly good answer to where are you and is less precise by nature.
_UK_POSTCODE = re.compile(r"^\s*([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})?\s*$", re.I)


async def geocode_postcode(session, text):
    """UK postcode to coordinates, or None if it is not one."""
    m = _UK_POSTCODE.match(text)
    if not m:
        return None
    out, inn = m.group(1).upper(), (m.group(2) or "").upper()
    url = (f"https://api.postcodes.io/postcodes/{out}{inn}" if inn
           else f"https://api.postcodes.io/outcodes/{out}")
    try:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            d = (await r.json()).get("result") or {}
    except Exception:
        return None
    lat, lon = d.get("latitude"), d.get("longitude")
    if lat is None or lon is None:
        return None
    # str for a full postcode, LIST for an outcode — an outcode spans several
    # districts and postcodes.io says so by changing the type of the field.
    #
    # Taking the first of the list is how "SW1A" came back labelled
    # "Herefordshire, England" for a Welsh postcode: it does straddle the
    # border, and the first entry is not the answer, it is just first. When the
    # list disagrees with itself the honest label is no label.
    def one(v):
        if isinstance(v, list):
            distinct = {x for x in v if x}
            return distinct.pop() if len(distinct) == 1 else None
        return v

    where = ", ".join(x for x in (one(d.get("admin_district")),
                                  one(d.get("country"))) if x)
    # Rounded to about a kilometre before it is stored. A full postcode locates
    # a handful of houses; a forecast does not vary across one, so keeping the
    # exact figure would be recording precision the feature cannot use.
    return {"lat": round(lat, 2), "lon": round(lon, 2),
            "label": f"{out}{' ' + inn if inn else ''}"
                     + (f" ({where})" if where else "")}


async def geocode(session, place):
    """A place name or UK postcode to coordinates, or None.

    Retries on the part before the first comma. Open-Meteo matches a single
    place name and returns nothing at all for "Keswick, Cumbria" — which is how
    a person writes it, and precisely when they are disambiguating.

    The qualifier is then used rather than discarded. Dropping it and taking
    the first global match sent the forecast to Keswick, Iowa: the county was
    the one piece of information that said which Keswick, and the retry threw
    it away. So the retry asks for ten and prefers one whose region or country
    contains the words that were dropped.
    """
    postcode = await geocode_postcode(session, place)
    if postcode:
        return postcode

    head, _, qualifier = place.partition(",")
    qualifier = qualifier.strip().lower()

    # Home country first, then the world.
    #
    # Open-Meteo ranks by population, which is overwhelmingly American: asking
    # for "Boston" returns Massachusetts, New York, Georgia, Kentucky, Indiana
    # and Virginia before Lincolnshire appears at all, so filtering the top ten
    # for the county cannot rescue it. Scoping the search fixes it at source.
    #
    # The fallback to an unscoped search is what keeps this a preference rather
    # than a restriction — "Reykjavik" still resolves.
    async def search(name, count, country=None):
        params = {"name": name, "count": count, "language": "en",
                  "format": "json"}
        if country:
            params["countryCode"] = country
        try:
            async with session.get(GEOCODE_URL, params=params) as r:
                return (await r.json()).get("results") or []
        except Exception:
            return None

    async def search_local_first(name, count):
        if HOME_COUNTRY:
            near = await search(name, count, HOME_COUNTRY)
            if near:
                return near
        return await search(name, count)

    if qualifier:
        # Always the wider search when a qualifier was given, never the comma
        # string. Open-Meteo returns nothing for "Keswick, Cumbria" but DOES
        # return something for "Boston, Lincolnshire" — Boston, Massachusetts.
        # A confident wrong answer is the worse of the two failures, so the
        # qualifier decides whenever there is one.
        wider = await search_local_first(head.strip(), 10)
        if not wider:
            return None

        def matches(c):
            where = " ".join(str(c.get(k) or "") for k in
                             ("admin1", "admin2", "admin3", "country")).lower()
            return any(w in where for w in qualifier.split() if len(w) > 2)

        res = [c for c in wider if matches(c)] or wider[:1]
    else:
        res = await search_local_first(place, 1)
    if not res:
        return None
    top = res[0]
    label = ", ".join(x for x in (top.get("name"), top.get("admin1"),
                                  top.get("country")) if x)
    return {"lat": top["latitude"], "lon": top["longitude"], "label": label}


async def weather_line(session, brief=False):
    """One or two sentences of weather, or a note that nowhere is set."""
    loc = load_state().get("location")
    if not loc:
        # A town, not a postcode: Open-Meteo's geocoder indexes settlements and
        # returns nothing for a UK postcode, so asking for one would be asking
        # for the input most likely to fail.
        return ("I don't know where you are. Say: set location "
                "<postcode or town>.")
    try:
        async with session.get(FORECAST_URL, params={
                "latitude": loc["lat"], "longitude": loc["lon"],
                "current": "temperature_2m,apparent_temperature,weather_code",
                # Hourly, because the daily figure is the wrong question — see
                # rain_ahead below.
                "hourly": "precipitation_probability",
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "forecast_days": 2, "timezone": "auto"}) as r:
            d = await r.json()
    except Exception as exc:
        return f"I couldn't reach the forecast ({type(exc).__name__})."

    cur, day = d.get("current") or {}, d.get("daily") or {}
    now_c = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    hi = (day.get("temperature_2m_max") or [None])[0]
    lo = (day.get("temperature_2m_min") or [None])[0]
    # The CURRENT code, not the day's. The daily code summarises midnight to
    # midnight, so a wet night made a bright afternoon read as "drizzle".
    sky = describe(cur.get("weather_code", 0))

    bits = [f"{loc['label']}: {now_c:.0f} degrees, {sky}" if now_c is not None
            else f"{loc['label']}: {sky}"]
    # Only when it disagrees with the real temperature by enough to matter —
    # "3 degrees, feels like 3" is noise.
    if feels is not None and now_c is not None and abs(feels - now_c) >= 2:
        bits.append(f"feels like {feels:.0f}")
    if hi is not None and lo is not None:
        bits.append(f"{lo:.0f} to {hi:.0f} today")
    line = ", ".join(bits) + ". " + rain_ahead(d.get("hourly") or {})
    return ("Morning. " + line) if brief else line


def rain_ahead(hourly, hours=12, now=None):
    """Chance of rain in the hours STILL TO COME, and roughly when.

    This used to be Open-Meteo's precipitation_probability_max, which is the
    maximum across the whole calendar day — INCLUDING hours already gone. At
    half eleven on a bright morning it reported "100% chance of rain" because
    it had rained at midnight, and every remaining hour of that day was between
    zero and four per cent. Reported honestly, and consistently wrong.

    A forecast is about the future. So the hours before now are dropped and the
    peak of what is left is what gets said, with the hour it falls in, because
    "60% at four" is a different afternoon from "60% at ten tonight".
    """
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    if not times or len(times) != len(probs):
        return ""

    # now is injectable so this can be tested against fixed hours. Reaching for
    # the wall clock inside made the only interesting cases — "it rained at
    # midnight and it is now noon" — untestable except at midnight and noon.
    now = now or time.strftime("%Y-%m-%dT%H:00")
    ahead = [(t, p) for t, p in zip(times, probs) if t >= now and p is not None]
    if not ahead:
        return ""
    ahead = ahead[:hours]

    peak_t, peak = max(ahead, key=lambda x: x[1])
    if peak < 15:
        return "Dry for the next few hours."
    when = peak_t[11:16]
    # "Rain" only once it is likelier than not; below that it is a risk, and
    # saying rain for a 30% chance is how a forecast stops being believed.
    word = "Rain likely" if peak >= 60 else "Rain possible" if peak >= 40 \
        else "Small chance of rain"
    return f"{word} around {when}, {peak:.0f}%."


def _plus_minutes(hhmm, minutes):
    """"07:30" plus 30 -> "08:00". Clamped, not wrapped: a window that crosses
    midnight would compare wrongly as a string, and 23:59 is a fine ceiling."""
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except Exception:
        return "23:59"
    total = min(h * 60 + m + minutes, 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}"


async def watch_brief(session):
    """Send the morning brief once a day, at the configured local time.

    Checks the clock rather than sleeping until the target, so a restart at
    07:29 does not lose the day's brief and a restart at 07:31 does not fire a
    second one — the date it last sent is persisted, and that is what decides.
    """
    while True:
        try:
            state = load_state()
            today = time.strftime("%Y-%m-%d")
            # A WINDOW, not "past the time". The first version asked whether
            # the clock had gone beyond 07:30, which is true for the rest of
            # the day — so restarting at half two in the afternoon sent a
            # "Morning." brief. Thirty minutes is long enough to survive a
            # restart across the target and short enough that a late one is
            # never a surprise.
            due = BRIEF_AT <= time.strftime("%H:%M") <= _plus_minutes(BRIEF_AT, 30)
            # Nowhere set means nothing worth saying. The brief would be a
            # daily reminder that it does not know where you are.
            if (due and state.get("brief_sent") != today and allowed()
                    and state.get("location")):
                line = await weather_line(session, brief=True)
                _, health = await health_line(session)
                for chat in sorted(allowed()):
                    await send(session, chat, line + "\n\n" + health)
                state = load_state()          # re-read: watch_health also writes
                state["brief_sent"] = today
                save_state(state)
                log(f"morning brief sent to {len(allowed())} chat(s)")
        except Exception as exc:
            log(f"brief failed: {type(exc).__name__}: {exc}")
        await asyncio.sleep(60)


# --- health -----------------------------------------------------------------

async def health_line(session):
    """One sentence on how Nova is, assembled here rather than by the model.

    Status is a question with a correct answer, and a 3B asked to summarise a
    health blob will occasionally invent a reassuring one. The page settled
    this the same way.
    """
    try:
        async with session.get(HEALTH_URL) as r:
            h = await r.json()
    except Exception as exc:
        return "down", f"I cannot reach my own health endpoint ({type(exc).__name__})."

    failing = h.get("failing") or []
    backup = (h.get("checks") or {}).get("backup") or {}
    age = backup.get("age_hours")
    parts = ["Not well: " + ", ".join(failing) + " failing."] if failing \
        else ["All services responding."]
    if isinstance(age, (int, float)):
        parts.append(f"Last backup {age:.0f} hours ago"
                     + (f", {backup.get('notes')} notes." if backup.get("notes") else "."))
    return (h.get("state") or "unknown"), " ".join(parts)


async def watch_health(session):
    """Speak up when something changes, and only then.

    Alerting on STATE rather than on a transition is how a monitor becomes
    noise: a backup that has been broken since Tuesday would message every five
    minutes until it was fixed or muted, and a muted alert is no alert. So the
    last state is persisted, and a message is sent when it differs — including
    the recovery, because knowing it came back matters as much as knowing it
    went.
    """
    while True:
        try:
            state = load_state()
            now, line = await health_line(session)
            if now != state.get("health"):
                was = state.get("health")
                if was is not None:      # never alert on first boot
                    for chat in sorted(allowed()):
                        await send(session, chat,
                                   ("Recovered. " if now == "ok" else "Something is wrong. ")
                                   + line)
                state["health"] = now
                save_state(state)
        except Exception:
            pass
        await asyncio.sleep(HEALTH_EVERY)


# --- the turn ---------------------------------------------------------------

# Gates, not understanding. Each decides only THAT a capability is wanted; what
# it is wanted for is worked out afterwards, by the router or by the model.
#
# Order is load-bearing. "Is that in my notes?" contains the word "notes" and
# would otherwise be read as a request to write one — a question answered by
# creating a note is a strange kind of wrong.
_NOTE_CHECK = re.compile(
    r"\b(?:is|are|was|were|did)\b.{0,70}\b(?:in|on)\s+(?:my|the|your)?\s*"
    r"(?:notes|obsidian|vault)\b|^\s*(?:do i have|have i got)\b.+\bnotes?\b", re.I)
_NOTE_MAKE = re.compile(
    r"\b(?:note|jot|write (?:that|it|this) down|shopping list|make a list)\b"
    r"|^\s*(?:add|put|append|stick)\b.+\b(?:to|onto|into|in|on)\b.+"
    r"\b(?:note|list)\b", re.I)
_RESEARCH = re.compile(
    r"^\s*(?:research|look up|read up on|search (?:the )?web for|"
    r"what'?s the latest on)\s+(.+?)\s*[?.!]*\s*$", re.I)
# Anywhere in the sentence, not anchored at the front.
#
# The first version was "^(what's the )?(weather|forecast|temperature)", which
# is one phrasing and a single allowed prefix. "what the weather was like near
# me" missed it, fell through to the model, and got told Nova has no access to
# local weather — the feature exists, it was asked for plainly, and the answer
# was that it does not exist. That is the worst shape a narrow gate can fail
# in, and it is the second time one has been too tight.
_WEATHER = re.compile(
    r"\b(?:weather|forecast|temperature|raining|snowing)\b"
    r"|\bis it (?:going to )?(?:rain|snow|be )\w*"
    r"|\bhow (?:hot|cold|warm|wet) is it\b"
    r"|\bwhat'?s it like outside\b", re.I)

# Questions ABOUT weather rather than requests FOR it. These belong to the
# model and the vault: "how does weather forecasting work" is not a request for
# today's forecast, and answering it with the temperature would be its own kind
# of wrong.
#
# "the" is the entire difference and the first version got it backwards.
# "what is weather" asks for a definition; "what is THE weather" asks for the
# forecast — and that is the commonest way anybody asks. Treating them alike
# sent the plainest possible request to the model, which answered "I have no
# weather feed here, I am offline by design."
#
# So the article is what disqualifies the exclusion, not what it tolerates.
_NOT_WEATHER = re.compile(
    r"\bhow does .{0,20}weather\b|\bwhat causes\b|\bexplain\b"
    r"|\bwhat is (?:a |an )?(?:weather|forecast)\b(?! (?:like|today|now))"
    r"|\bweather (?:station|balloon|map|model|front|system|api)\b", re.I)


def wants_weather(text):
    return bool(_WEATHER.search(text)) and not _NOT_WEATHER.search(text)
_SET_LOC = re.compile(r"^\s*set (?:my )?location (?:to )?(.+?)\s*[.!]*\s*$", re.I)


async def research(session, chat, topic, spoken=False):
    """Vault, then the offline encyclopedia, then the web — and file the result.

    /research streams, and this does not: the caller is a chat message, which
    arrives whole or not at all. So the stream is consumed here and sent once.

    Web search is attempted but not required. The free engines rate-limit and
    CAPTCHA server traffic, and when they all refuse the router still answers
    from the vault and the offline archive — which is most of the value anyway.
    """
    text, note = "", None
    try:
        async with session.post(RESEARCH_URL,
                                json={"q": topic, "agent": "local", "web": True},
                                timeout=aiohttp.ClientTimeout(
                                    total=None, sock_read=600)) as r:
            if r.status == 404:
                return await send(session, chat,
                                  f"I found nothing on {topic}, anywhere.")
            async for raw in r.content:
                line = raw.decode("utf-8", "replace").strip()
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
                    text += d["choices"][0]["delta"].get("content", "") or ""
                except Exception:
                    pass
    except Exception as exc:
        return await send(session, chat,
                          f"The research call failed ({type(exc).__name__}).")

    text = text.strip()
    if not text:
        return await send(session, chat, f"I came up with nothing on {topic}.")
    if note and note.get("file"):
        text += f"\n\nFiled as {note['file']}."
    await send(session, chat, text)
    if spoken:
        await send_voice(session, chat, text)


async def answer(session, chat, text, spoken=False):
    low = text.strip().lower()

    # Deterministic commands, answered without the model for the same reason
    # the page does it: these have correct answers, and a small model asked to
    # report on itself will produce a plausible one instead.
    if low in ("status", "health", "what's wrong", "whats wrong"):
        _, line = await health_line(session)
        return await send(session, chat, line)
    if low in ("reset", "forget", "new chat"):
        _history.pop(chat, None)
        return await send(session, chat, "Cleared. Starting fresh.")
    if low in ("help", "commands", "what can you do"):
        return await send(session, chat, HELP)

    m = _SET_LOC.match(text)
    if m:
        loc = await geocode(session, m.group(1))
        if not loc:
            return await send(session, chat, f"I can't find {m.group(1)}.")
        state = load_state()
        state["location"] = loc
        save_state(state)
        log(f"location set for chat {chat}")
        return await send(session, chat,
                          f"Set to {loc['label']}. Morning brief at {BRIEF_AT}.")

    if wants_weather(text):
        return await send(session, chat, await weather_line(session))

    if _LIST_REM.match(text):
        rems = sorted((r for r in load_state().get("reminders", [])
                       if r["chat"] == str(chat)), key=lambda r: r["at"])
        if not rems:
            return await send(session, chat, "Nothing set.")
        return await send(session, chat, "\n".join(
            f"{r['id']}. {r['what']} — {when_words(r['at'])}" for r in rems))

    m = _CANCEL.match(text)
    if m:
        state = load_state()
        rems = state.get("reminders", [])
        target = m.group(1).lower()
        mine = [r for r in rems if r["chat"] == str(chat)]
        # Only ever this chat's own. The allowlist can hold more than one.
        drop = mine if target == "all" else [r for r in mine
                                             if str(r["id"]) == target]
        if not drop:
            return await send(session, chat, "Nothing matching that.")
        state["reminders"] = [r for r in rems if r not in drop]
        save_state(state)
        return await send(session, chat, f"Cancelled {len(drop)}.")

    m = _REMIND.match(text) or _TIMER.match(text)
    if m:
        rest = m.group(1)
        when, remainder = parse_when(rest)
        if not when:
            return await send(session, chat,
                              "When? Say \"in 20 minutes\" or \"at 7pm\".")
        what = clean_task(remainder) or "timer"
        rid = add_reminder(chat, when, what)
        log(f"reminder {rid} set for chat {chat}")
        return await send(session, chat,
                          f"Right — {what}, {when_words(when)}. (#{rid})")

    # Checked BEFORE the note-writing gate: see the note on ordering above.
    if _NOTE_CHECK.search(text):
        try:
            async with session.get(NOTES_URL, params={"q": text}) as r:
                hits = (await r.json()).get("hits") or []
        except Exception as exc:
            return await send(session, chat,
                              f"I couldn't read the vault ({type(exc).__name__}).")
        if not hits:
            return await send(session, chat, "No. Nothing in the vault matches that.")
        names = ", ".join(h["title"] for h in hits[:5])
        return await send(session, chat,
                          f"Yes — {names}." if len(hits) <= 5 else
                          f"Yes, {len(hits)} of them: {names}, and more.")

    if _NOTE_MAKE.search(text):
        try:
            async with session.post(NOTE_FROM_TEXT_URL, json={"text": text},
                                    timeout=aiohttp.ClientTimeout(
                                        total=None, sock_read=300)) as r:
                out = await r.json()
        except Exception as exc:
            return await send(session, chat,
                              f"I couldn't write that ({type(exc).__name__}).")
        if out.get("ok"):
            log(f"note {out['action']}: {out['file']}")
            # The exact contents, not a claim. A 3B extracting a note from a
            # sentence embellishes, and the whole reason this feature exists is
            # that it once said a note had been written when none had.
            return await send(session, chat,
                              f"{out['action'].capitalize()} \"{out['title']}\":\n\n"
                              f"{out['body']}")
        if out.get("error"):
            return await send(session, chat, f"I couldn't: {out['error']}")
        # "NONE" means the sentence merely mentioned a note — "note that TLS
        # 1.3 dropped renegotiation" is not a request to write one — so it
        # falls through to a normal answer.
        #
        # Anything else means it WAS a note request and the title and body
        # could not be pulled out of it, usually because several requests were
        # stacked in one sentence. That is a known state with a useful reply,
        # and handing it to the model instead produced "I don't know."
        if (out.get("raw") or "").strip().upper() != "NONE":
            return await send(session, chat,
                              "I can see you want a note, but not what to call "
                              "it. Try: make a note called X saying Y. One "
                              "thing at a time works best.")

    m = _RESEARCH.match(text)
    if m:
        topic = m.group(1)
        await send(session, chat, f"Looking into {topic}. This takes a minute.")
        return await research(session, chat, topic, spoken)

    body = {"q": text, "history": [{"role": r, "content": c}
                                   for r, c in _history.get(chat, [])]}
    try:
        async with session.post(ASK_URL, json=body,
                                timeout=aiohttp.ClientTimeout(total=None,
                                                              sock_read=300)) as r:
            out = await r.json()
    except Exception as exc:
        return await send(session, chat,
                          f"I could not reach my own router ({type(exc).__name__}).")

    reply = (out.get("answer") or "").strip()
    if not reply:
        return await send(session, chat, "I have no answer for that.")
    remember(chat, "user", text)
    remember(chat, "assistant", reply)

    # Text always: it is scannable, searchable in the chat history, and works
    # when a voice note cannot be played. The spoken copy is an addition for
    # someone who asked out loud, never a replacement.
    await send(session, chat, reply)
    if spoken:
        await send_voice(session, chat, reply)


async def handle(session, msg):
    chat = str((msg.get("chat") or {}).get("id", ""))
    if not chat:
        return
    text = (msg.get("text") or "").strip()
    voice = msg.get("voice") or msg.get("audio") or {}

    if chat not in allowed():
        # Rate limited BEFORE the code is checked, not after. Enrolment is the
        # one thing an unknown sender can attempt, so it is the one thing worth
        # brute forcing; without a ceiling here a stranger could try the code
        # as fast as the network allows and the allowlist would be the only
        # thing standing between them and the vault.
        if not rate_ok(chat):
            return
        reply = try_enrol(chat, text)
        if reply:
            log(f"enrolled chat {chat}")
            return await send(session, chat, reply)
        # A bare refusal rather than silence. The original reasoning — that
        # saying nothing tells a stranger nothing — was right about codes and
        # wrong about everything else: it also tells the OWNER nothing, and an
        # assistant that reads your message and does not respond is
        # indistinguishable from one that is broken. This reveals no more than
        # the fact they already have, which is that the bot exists.
        log(f"refused chat {chat}: not on the allowlist")
        return await send(session, chat, "Not authorised.")

    if not rate_ok(chat):
        return await send(session, chat, "Too many messages. Give me a minute.")

    if voice:
        if voice.get("duration", 0) > MAX_VOICE_S:
            return await send(session, chat,
                              f"That is longer than {MAX_VOICE_S} seconds. "
                              "Send me a shorter one.")
        heard = await voice_to_text(session, voice.get("file_id"))
        if not heard:
            return await send(session, chat,
                              "I could not make that out." if HAVE_FFMPEG else
                              "I cannot handle voice notes — no ffmpeg here.")
        # Echoed back so a mis-hearing is visible rather than mysterious: the
        # answer to a misheard question looks like a wrong answer.
        await send(session, chat, f"Heard: {heard}")
        return await answer(session, chat, heard, spoken=True)

    if text:
        await answer(session, chat, text)


async def poll():
    """Long poll for updates. Outbound only; nothing listens here."""
    offset = None
    log(f"bridge up: token={'yes' if token() else 'no'} "
        f"allowed={len(allowed())} enrol_code={'set' if ENROL_CODE else 'unset'} "
        f"ffmpeg={'yes' if HAVE_FFMPEG else 'no'}")
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=90)) as session:
        asyncio.create_task(watch_health(session))
        asyncio.create_task(watch_brief(session))
        asyncio.create_task(watch_reminders(session))
        while True:
            tok = token()
            if not tok:
                # No token yet is the normal state before enrolment, not an
                # error. Wait quietly rather than filling the log.
                await asyncio.sleep(30)
                continue
            try:
                params = {"timeout": 50}
                if offset is not None:
                    params["offset"] = offset
                async with session.get(
                        f"https://api.telegram.org/bot{tok}/getUpdates",
                        params=params) as r:
                    data = await r.json()
            except Exception:
                await asyncio.sleep(5)
                continue

            if data.get("result"):
                log(f"{len(data['result'])} update(s)")
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                # Wrapped, because an exception inside a bare create_task is
                # swallowed by the event loop and vanishes. That is how a
                # handler could fail on every message while the bridge looked
                # perfectly healthy from the outside.
                asyncio.create_task(guarded(session, msg))


async def guarded(session, msg):
    try:
        await handle(session, msg)
    except Exception as exc:
        chat = str((msg.get("chat") or {}).get("id", "?"))
        log(f"handler failed for chat {chat}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(poll())
