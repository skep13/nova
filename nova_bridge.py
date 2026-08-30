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
import shutil
import subprocess
import tempfile
import time

import aiohttp

ASK_URL = os.environ.get("NOVA_ASK_URL", "http://remote:5003/ask")
HEALTH_URL = os.environ.get("NOVA_HEALTH_URL", "http://remote:5003/health")
STT_URL = os.environ.get("NOVA_STT_URL", "http://whisper:8080/inference")
TTS_URL = os.environ.get("NOVA_TTS_URL", "http://piper:5000/synthesize")
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
    if text.strip() != ENROL_CODE:
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

async def answer(session, chat, text, spoken=False):
    low = text.strip().lower()

    # Deterministic commands, answered without the model for the same reason
    # the page does it: these have correct answers, and a small model asked to
    # report on itself will produce a plausible one instead.
    if low in ("status", "health", "what's wrong", "whats wrong", "how are you"):
        _, line = await health_line(session)
        return await send(session, chat, line)
    if low in ("reset", "forget", "new chat"):
        _history.pop(chat, None)
        return await send(session, chat, "Cleared. Starting fresh.")

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
        # Silence otherwise, not an explanation. An unknown sender who is told
        # a code exists has been told what to try next.
        return await send(session, chat, reply) if reply else None

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
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=90)) as session:
        asyncio.create_task(watch_health(session))
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

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                asyncio.create_task(handle(session, msg))


if __name__ == "__main__":
    asyncio.run(poll())
